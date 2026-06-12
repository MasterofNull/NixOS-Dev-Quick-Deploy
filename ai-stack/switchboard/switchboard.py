#!/usr/bin/env python3
"""AI Switchboard — OpenAI-compatible LLM routing proxy."""
import sys
from pathlib import Path

# Stability Backbone (Phase 55.2): Ensure shared utilities are on path
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SHARED_PATH = str(_REPO_ROOT / "ai-stack" / "mcp-servers")
if _SHARED_PATH not in sys.path:
    sys.path.insert(0, _SHARED_PATH)
_LIB_PATH = str(_REPO_ROOT / "scripts" / "ai" / "lib")
if _LIB_PATH not in sys.path:
    sys.path.insert(0, _LIB_PATH)

import agent_run_events as _are

import asyncio
import collections
import hashlib
import threading
import os
import json
import re
import sys
import time
import math
import datetime
import pathlib
from typing import Optional, Union, Dict, List
from urllib.parse import urlparse

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

# Stability Backbone (Phase 55.2)
from shared.circuit_breaker import CircuitBreakerRegistry, CircuitBreakerError, CircuitState, CircuitBreakerOpenError
from shared.llm_config import build_llama_payload
from shared.retry_backoff import retry_with_backoff

# Configuration from Environment
LLAMA_URL = os.environ.get("LLAMA_CPP_URL", "http://127.0.0.1:8080").rstrip("/")
EMBEDDING_URL = os.environ.get("EMBEDDING_URL", "").rstrip("/")
REMOTE_URL = os.environ.get("REMOTE_LLM_URL", "").rstrip("/")
ROUTING_MODE = os.environ.get("ROUTING_MODE", "auto").strip().lower()
DEFAULT_PROVIDER = os.environ.get("DEFAULT_PROVIDER", "local").strip().lower()
REMOTE_API_KEY = os.environ.get("REMOTE_LLM_API_KEY", "").strip()
REMOTE_API_KEY_FILE = os.environ.get("REMOTE_LLM_API_KEY_FILE", "").strip()
PORT = int(os.environ.get("PORT", "8085"))
HOST = os.environ.get("HOST", "127.0.0.1")
ROUTE_HINT_HEADER = "x-ai-route"
PROVIDER_HINT_HEADER = "x-ai-provider"
PROFILE_HINT_HEADER = "x-ai-profile"

_AGENT_RUN_EVENTS_PATH = Path(
    os.getenv("AQ_AGENT_RUN_EVENTS_PATH", "/var/lib/ai-stack/hybrid/telemetry/agent-run-events.jsonl")
)
_THINK_BLOCK_RE = re.compile(r"<think>(.*?)</think>", flags=re.DOTALL | re.IGNORECASE)


async def _emit_reasoning_summary_events(run_id: str, content: str) -> str:
    """Emit safe reasoning-observed events and remove raw reasoning blocks.

    The dashboard should show that a local model produced internal reasoning,
    but it must not persist or display raw chain-of-thought. Store a hash and
    size for traceability instead.
    """
    if not content or "<think" not in content.lower():
        return content

    matches = list(_THINK_BLOCK_RE.finditer(content))
    for match in matches:
        raw_thought = (match.group(1) or "").strip()
        if not raw_thought:
            continue
        try:
            ev = _are.make_event(
                event_type="thought",
                source="switchboard",
                run_id=run_id,
                payload={
                    "kind": "local_model_reasoning_block",
                    "summary": "Local model emitted an internal reasoning block; raw chain-of-thought was suppressed.",
                    "char_count": len(raw_thought),
                    "content_hash": _are.stable_digest(raw_thought),
                    "redaction_level": "raw_reasoning_suppressed",
                },
            )
            await asyncio.to_thread(_are.append_jsonl, _AGENT_RUN_EVENTS_PATH, ev)
        except Exception as e:
            print(f"[switchboard] failed to emit thought summary event: {e}", file=sys.stderr)

    return _THINK_BLOCK_RE.sub("", content).strip()

# Initialize Independent Circuit Breaker Registries
# Phase 56.1: Decouple local and remote paths to prevent downstream provider failures 
# from blocking local inference/tooling.
LOCAL_CIRCUIT_BREAKERS = CircuitBreakerRegistry(
    default_config={
        "failure_threshold": int(os.getenv("SWITCHBOARD_CB_FAILURE_THRESHOLD", "5")),
        "reset_timeout": float(os.getenv("SWITCHBOARD_CB_RESET_TIMEOUT", "30.0")),
        "success_threshold": int(os.getenv("SWITCHBOARD_CB_SUCCESS_THRESHOLD", "2")),
    }
)
REMOTE_CIRCUIT_BREAKERS = CircuitBreakerRegistry(
    default_config={
        "failure_threshold": int(os.getenv("SWITCHBOARD_CB_FAILURE_THRESHOLD", "5")),
        "reset_timeout": float(os.getenv("SWITCHBOARD_CB_RESET_TIMEOUT", "30.0")),
        "success_threshold": int(os.getenv("SWITCHBOARD_CB_SUCCESS_THRESHOLD", "2")),
    }
)

REMOTE_MODEL_PREFIXES = (
    "remote/",
    "openai/",
    "anthropic/",
    "openrouter/",
    "custom/",
)

HYBRID_COORDINATOR_URL = os.environ.get("HYBRID_COORDINATOR_URL", os.environ.get("HYBRID_URL", "")).rstrip("/")
HYBRID_URL = HYBRID_COORDINATOR_URL  # deprecated alias — use HYBRID_COORDINATOR_URL
HINTS_INJECT = os.environ.get("HINTS_INJECT", "1").strip() not in ("0", "false", "no")
HINTS_LIMIT = int(os.environ.get("HINTS_LIMIT", "2"))

# Profile Card Definitions (Ported from Nix)
DEFAULT_PROFILE_CARD = """/no_think
[profile-card:default]
You are AQ, an expert coding and systems developer. You are proficient in NixOS and grounded in the NixOS-Dev-Quick-Deploy harness.

MANDATORY: Show your work with proof (als, agrep, read_file) and CHECK-IN with a plan before acting.

=== COMMON TASKS ===
PRSI / Optimization: run: scripts/automation/prsi-orchestrator.py list
Service Health: run: aq-qa 0
Search Code: run: agrep "<keyword>" . --include="*.py"
Knowledge: run: query_aidb {query: "<q>"}

Key dirs: scripts/ai/, scripts/agent-tools/, ai-stack/mcp-servers/, nix/modules/, dashboard/, config/
Ports: llama:8080 aidb:8002 hybrid:8003 ralph:8004 swb:8085 dashboard:8889
"""

CONTINUE_LOCAL_CARD = """/no_think
[profile-card:continue-local]
Concise. als/agrep first — never browse blindly. Act, don't restate.
PRSI: /var/lib/nixos-ai-stack/prsi/action-queue.json | aq-hints "<q>" | aq-qa 0
"""

HARNESS_AWARE_BODY = """You are AQ, an expert coding and systems developer embedded in the NixOS-Dev-Quick-Deploy harness. You are proficient in NixOS and autonomous AI orchestration.

=== OPERATIONAL GUIDELINES ===
- CHECK-IN FIRST: Before making system changes, show your research and proposed plan with proof (file reads, command outputs).
- EVIDENCE-BASED: Ground every answer in the actual system state using tools.
- NIXOS MASTERY: Apply best practices for NixOS, Flakes, and declarative configuration.
- PRECISION: Never guess; search and verify first.

=== TASK → FIRST ACTIONS ===
Self-Improvement Slice ("run a self improvement slice"):
  STEP 1: read_file(".agent/memory/issues-backlog.md") — find highest-priority OPEN issues
  STEP 2: read_file(".agent/collaboration/RESUME.json") — check in-progress objectives
  STEP 3: read_file(".agent/collaboration/HANDOFF.md") — see what was done last session
  STEP 4: read_file(".agents/plans/") or list latest .md plans for roadmap context
  STEP 5: PROPOSE 3 ranked options (effort × impact) — include which files would change
  STEP 6: WAIT for operator to choose before executing any changes
  !! NEVER treat uncommitted git changes as the improvement target !!
  !! NEVER default to documentation cleanup or commit leftover files !!

Service Health:
  MCP tool: harness_health -> then journalctl -u ai-*.service -n 50 --no-pager

Knowledge Retrieval:
  MCP tool: query_aidb {query: "<question>"} (vector search)
  MCP tool: get_hint {query: "<task summary>"} (pattern lookup)

Project Exploration:
  1. Use als -d 1 or search_files for orientation.
  2. Use read_file (or acat) to provide proof of current state.

=== COMMIT RULES ===
git add <specific files> && scripts/governance/tier0-validation-gate.sh --pre-commit && git commit -m "type(scope): msg\\n\\nCo-Authored-By: AQ <noreply@harness.local>"
"""

LOCAL_AGENT_CARD = f"""/no_think
[profile-card:local-agent]
{HARNESS_AWARE_BODY}
"""

REMOTE_DEFAULT_CARD = """[profile-card:remote-default]
Optimize for token efficiency.
Use brief answers first, expand only when requested.
Avoid restating long policy docs unless explicitly asked.
"""

REMOTE_GEMINI_CARD = f"""[profile-card:remote-gemini]
Use Gemini as the front-door remote orchestration lane for discovery, planning, and synthesis.
{HARNESS_AWARE_BODY}
Keep the output handoff-ready and explicitly trigger local tools, embeddings, or local models when they should take over.
"""

REMOTE_FREE_CARD = """[profile-card:remote-free]
Use low-cost or free remote capacity for probing, not for unrestricted context bloat.
Keep prompts compact and prefer retrieval before raising token spend.
"""

REMOTE_CODING_CARD = """[profile-card:remote-coding]
Use the configured coding-optimized remote model for concrete implementation help.
Keep file scope explicit and avoid broad background dumps.
"""

REMOTE_REASONING_CARD = """[profile-card:remote-reasoning]
Use the configured higher-judgment remote model for architecture, policy, and tradeoff work.
Spend tokens intentionally and only after scoping the decision clearly.
"""

REMOTE_TOOL_CALLING_CARD = """[profile-card:remote-tool-calling]
Use the configured remote tool-calling lane for bounded tool use with strict arguments.
Prefer minimal tool schemas, explicit constraints, and concise final output.
"""

LOCAL_TOOL_CALLING_CARD = """[profile-card:local-tool-calling]
Use the local tool-calling lane for bounded built-in tool execution on the local host.
The runtime leases a small active tool set; use the leased tools for evidence, then synthesize.
For broad analysis, gather only the strongest 2-4 evidence points before answering.
Use lease_tools to swap to a different active bundle when the current leased tools are the wrong fit.
Preserve strict tool schemas, prefer concise execution, and surface tool failures explicitly.
CRITICAL: Issue the tool call directly — do not announce it, do not self-correct, do not loop.
"""

EMBEDDING_LOCAL_CARD = """[profile-card:embedding-local]
Embeddings profile: retrieval/ranking only, not chat reasoning.
Prioritize progressive disclosure by selecting only relevant chunks.
"""

EMBEDDED_ASSIST_CARD = """/no_think
[profile-card:embedded-assist]
Use compact reasoning and progressive disclosure.
Prefer hybrid retrieval (semantic + lexical), then ask for clarification on low confidence.
Do not expand full policy docs unless explicitly requested.
CRITICAL: Act immediately on each turn. Never repeat a stated intention more than once — if you said you will do something, do it now.
SEARCH-FIRST RULE: Before answering any question about project files, services, or code — run a als or agrep lookup. Never say "I see the project structure, what would you like to do?" — search, read, then act.
Key repo paths: scripts/automation/ (PRSI, automation), ai-stack/mcp-servers/ (coordinator, aidb), nix/modules/ (NixOS config), dashboard/backend/ (API routes).
"""

LLAMA_CTX_SIZE = int(os.environ.get("LLAMA_CTX_SIZE", "8192"))

DEFAULT_PROFILE_CATALOG = {
    "default": {
        "forceProvider": None,
        "injectHints": True,
        "modelAlias": None,
        "advertisedContextWindow": LLAMA_CTX_SIZE,
        "maxInputTokens": 1500,
        "maxMessages": 12,
        "maxOutputTokens": 768,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": DEFAULT_PROFILE_CARD,
    },
    "continue-local": {
        "forceProvider": "local",
        "injectHints": True,
        "modelAlias": None,
        "advertisedContextWindow": LLAMA_CTX_SIZE,
        "maxInputTokens": int(os.environ.get("SWB_CONTINUE_LOCAL_MAX_INPUT_TOKENS", "4000")),
        "maxMessages": int(os.environ.get("SWB_CONTINUE_LOCAL_MAX_MESSAGES", "12")),
        "maxOutputTokens": 768,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": CONTINUE_LOCAL_CARD,
    },
    "local-agent": {
        "forceProvider": "local",
        "injectHints": True,
        "modelAlias": None,
        "advertisedContextWindow": LLAMA_CTX_SIZE,
        "maxInputTokens": 8000,
        "maxMessages": 16,
        "maxOutputTokens": 4096,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": LOCAL_AGENT_CARD,
    },
    "remote-default": {
        "forceProvider": "remote",
        "injectHints": False,
        "modelAlias": None,
        "advertisedContextWindow": None,
        "maxInputTokens": 3500,
        "maxMessages": 16,
        "maxOutputTokens": 2048,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": REMOTE_DEFAULT_CARD,
    },
    "remote-gemini": {
        "forceProvider": "remote",
        "injectHints": False,
        "modelAlias": os.environ.get("SWB_REMOTE_MODEL_ALIAS_GEMINI", os.environ.get("SWB_REMOTE_MODEL_ALIAS_FREE")),
        "advertisedContextWindow": None,
        "maxInputTokens": 3500,
        "maxMessages": 16,
        "maxOutputTokens": 1400,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": REMOTE_GEMINI_CARD,
    },
    "remote-free": {
        "forceProvider": "remote",
        "injectHints": False,
        "modelAlias": os.environ.get("SWB_REMOTE_MODEL_ALIAS_FREE"),
        "advertisedContextWindow": None,
        "maxInputTokens": 3500,
        "maxMessages": 16,
        "maxOutputTokens": 1200,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": REMOTE_FREE_CARD,
    },
    "remote-coding": {
        "forceProvider": "remote",
        "injectHints": False,
        "modelAlias": os.environ.get("SWB_REMOTE_MODEL_ALIAS_CODING"),
        "advertisedContextWindow": None,
        "maxInputTokens": 5000,
        "maxMessages": 20,
        "maxOutputTokens": 1800,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": REMOTE_CODING_CARD,
    },
    "remote-reasoning": {
        "forceProvider": "remote",
        "injectHints": False,
        "modelAlias": os.environ.get("SWB_REMOTE_MODEL_ALIAS_REASONING"),
        "advertisedContextWindow": None,
        "maxInputTokens": 6000,
        "maxMessages": 20,
        "maxOutputTokens": 1800,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": REMOTE_REASONING_CARD,
    },
    "remote-tool-calling": {
        "forceProvider": "remote",
        "injectHints": False,
        "modelAlias": os.environ.get("SWB_REMOTE_MODEL_ALIAS_TOOL_CALLING"),
        "advertisedContextWindow": None,
        "maxInputTokens": 3500,
        "maxMessages": 16,
        "maxOutputTokens": 900,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": REMOTE_TOOL_CALLING_CARD,
    },
    "local-tool-calling": {
        "forceProvider": "local",
        "injectHints": True,
        "modelAlias": None,
        "advertisedContextWindow": LLAMA_CTX_SIZE,
        # 12000 input + 1024 output = 13024 < 16384 ctx headroom; env-override for rebuild flexibility
        "maxInputTokens": int(os.environ.get("SWB_LOCAL_TOOL_MAX_INPUT_TOKENS", "12000")),
        "maxMessages": 20,
        "maxOutputTokens": int(os.environ.get("SWB_LOCAL_TOOL_MAX_OUTPUT_TOKENS", "2048")),
        "embeddingsOnly": False,
        "toolExecution": "built-in",
        "profileCard": LOCAL_TOOL_CALLING_CARD,
    },
    "embedding-local": {
        "forceProvider": "local",
        "injectHints": False,
        "modelAlias": None,
        "advertisedContextWindow": 512,
        "maxInputTokens": 512,
        "maxMessages": 8,
        "maxOutputTokens": 256,
        "embeddingsOnly": True,
        "toolExecution": None,
        "profileCard": EMBEDDING_LOCAL_CARD,
    },
    "embedded-assist": {
        "forceProvider": "local",
        "injectHints": False,
        "modelAlias": None,
        "advertisedContextWindow": LLAMA_CTX_SIZE,
        "maxInputTokens": 3000,
        "maxMessages": 12,
        "maxOutputTokens": 1024,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": EMBEDDED_ASSIST_CARD,
    },
    "coordinator-internal": {
        "forceProvider": "local",
        "injectHints": False,
        "modelAlias": None,
        "advertisedContextWindow": LLAMA_CTX_SIZE,
        "maxInputTokens": 8000,
        "maxMessages": 20,
        "maxOutputTokens": 4096,
        "embeddingsOnly": False,
        "toolExecution": None,
        "profileCard": "",
    },
}

def _load_profile_catalog() -> dict:
    catalog = DEFAULT_PROFILE_CATALOG.copy()
    loaded = {}

    yaml_file = os.environ.get("SWB_PROFILE_CATALOG_YAML_FILE", "").strip()
    if yaml_file:
        try:
            import yaml
            with open(yaml_file, "r", encoding="utf-8") as handle:
                doc = yaml.safe_load(handle)
            if isinstance(doc, dict) and isinstance(doc.get("profiles"), dict):
                loaded = doc["profiles"]
            elif isinstance(doc, dict):
                loaded = doc
        except (OSError, Exception) as exc:
            print(f"warning: failed to load switchboard profile catalog YAML: {exc}", file=sys.stderr)
    else:
        catalog_file = os.environ.get("SWB_PROFILE_CATALOG_JSON_FILE", "").strip()
        if catalog_file:
            try:
                with open(catalog_file, "r", encoding="utf-8") as handle:
                    loaded = json.load(handle)
            except (OSError, json.JSONDecodeError) as exc:
                print(f"warning: failed to load switchboard profile catalog file: {exc}", file=sys.stderr)
        else:
            raw_catalog = os.environ.get("SWB_PROFILE_CATALOG_JSON", "{}") or "{}"
            try:
                loaded = json.loads(raw_catalog)
            except json.JSONDecodeError as exc:
                print(f"warning: invalid SWB_PROFILE_CATALOG_JSON, falling back to empty catalog: {exc}", file=sys.stderr)

    if isinstance(loaded, dict):
        for name, value in loaded.items():
            if name.startswith("_"):
                continue  # skip _meta and other YAML metadata keys
            if name in catalog and isinstance(catalog[name], dict) and isinstance(value, dict):
                # Merge: null values in YAML preserve Python defaults (env-var-resolved fields)
                catalog[name].update({k: v for k, v in value.items() if v is not None})
            else:
                catalog[name] = value

    # Startup validation: warn if token budget exceeds context window headroom
    budget_ctx = LLAMA_CTX_SIZE - 600
    for pname, psettings in catalog.items():
        if not isinstance(psettings, dict):
            continue
        if psettings.get("embeddingsOnly") or psettings.get("forceProvider") == "remote":
            continue
        max_in = psettings.get("maxInputTokens") or 0
        max_out = psettings.get("maxOutputTokens") or 0
        if isinstance(max_in, int) and isinstance(max_out, int) and max_in + max_out > budget_ctx:
            print(
                f"warning: profile '{pname}' token budget ({max_in}+{max_out}={max_in+max_out}) "
                f"exceeds LLAMA_CTX_SIZE-600={budget_ctx}; consider reducing maxInputTokens or maxOutputTokens",
                file=sys.stderr,
            )

    return catalog


def _load_routing_rules() -> dict:
    """Load routing_rules from harness-prompt-extensions.json/yaml if present."""
    repo_path = os.environ.get("REPO_PATH", "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy")
    for candidate in (
        os.path.join(repo_path, "config", "harness-prompt-extensions.json"),
        os.path.join(repo_path, "config", "harness-prompt-extensions.yaml"),
    ):
        if not os.path.exists(candidate):
            continue
        try:
            with open(candidate, "r", encoding="utf-8") as fh:
                raw = fh.read()
            doc: dict = {}
            try:
                import yaml as _yaml
                doc = _yaml.safe_load(raw) or {}
            except Exception:
                doc = json.loads(raw)
            if isinstance(doc, dict) and isinstance(doc.get("routing_rules"), dict):
                return doc["routing_rules"]
        except Exception as exc:
            print(f"warning: failed to load routing_rules: {exc}", file=sys.stderr)
    return {}


def _classify_routing_intent(payload: dict | None) -> str | None:
    """Return 'local' or 'remote' based on routing_rules task_matrix, or None to defer.

    Checks:
    1. Input token count against local_input_token_limit (hard cap → remote).
    2. Prompt text against task_matrix triggers (first match wins, remote tasks checked first).
    Returns None when no rule fires — caller falls through to DEFAULT_PROVIDER logic.
    """
    if not isinstance(payload, dict):
        return None
    rules = ROUTING_RULES
    if not rules:
        return None

    # Hard token-count cap: anything over limit goes remote
    token_limit = int(rules.get("local_input_token_limit", 8000))
    messages = payload.get("messages") or []
    if isinstance(messages, list):
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        # Rough approximation: 4 chars ≈ 1 token
        estimated_tokens = total_chars // 4
        if estimated_tokens > token_limit and REMOTE_URL:
            return "remote"

    # Prompt text trigger matching
    prompt_text = " ".join(
        str(m.get("content", "")) for m in messages if isinstance(m, dict)
    ).lower()
    task_matrix = rules.get("task_matrix", {})
    # Check remote-forcing rules first so they take precedence
    for task_type, spec in task_matrix.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("provider") != "remote":
            continue
        if any(trigger in prompt_text for trigger in spec.get("triggers", [])):
            return "remote" if REMOTE_URL else "local"
    # Then check local-preferred rules
    for task_type, spec in task_matrix.items():
        if not isinstance(spec, dict):
            continue
        if spec.get("provider") != "local":
            continue
        if any(trigger in prompt_text for trigger in spec.get("triggers", [])):
            return "local"
    return None


PROFILE_CATALOG = _load_profile_catalog()
ROUTING_RULES = _load_routing_rules()
REPO_PATH = os.environ.get("REPO_PATH", "/home/hyperd/Documents/NixOS-Dev-Quick-Deploy")
LOCAL_AGENTS_PATH = os.environ.get("LOCAL_AGENTS_PATH", f"{REPO_PATH}/ai-stack/local-agents").strip()
LOCAL_TOOL_CALL_LIMIT = int(os.environ.get("SWB_LOCAL_TOOL_CALL_LIMIT", "40"))
ACTIVE_TOOL_SCHEMA_LIMIT = max(1, int(os.environ.get("SWB_ACTIVE_TOOL_SCHEMA_LIMIT", "12")))
TOOL_WORKING_SET_ENABLED = os.environ.get("SWB_TOOL_WORKING_SET_ENABLED", "1").strip() not in ("0", "false", "no")
REMOTE_TOOL_WORKING_SET_ENABLED = os.environ.get("SWB_REMOTE_TOOL_WORKING_SET_ENABLED", "1").strip() not in ("0", "false", "no")
CONTEXT_OUTPUT_GC_ENABLED = os.environ.get("SWB_CONTEXT_OUTPUT_GC_ENABLED", "1").strip() not in ("0", "false", "no")
CONTEXT_OUTPUT_GC_MIN_CHARS = max(256, int(os.environ.get("SWB_CONTEXT_OUTPUT_GC_MIN_CHARS", "5000")))
CONTEXT_OUTPUT_GC_SUMMARY_CHARS = max(160, int(os.environ.get("SWB_CONTEXT_OUTPUT_GC_SUMMARY_CHARS", "900")))
CONTEXT_ARTIFACT_DIR = os.environ.get(
    "SWB_CONTEXT_ARTIFACT_DIR",
    "/home/hyperd/.local/share/nixos-ai-stack/local-agents/switchboard-artifacts",
).strip()
TOOL_RESULT_DEDUPE_ENABLED = os.environ.get("SWB_TOOL_RESULT_DEDUPE_ENABLED", "1").strip() not in ("0", "false", "no")
CONNECT_TIMEOUT_S = float(os.environ.get("SWB_CONNECT_TIMEOUT_S", "10"))
WRITE_TIMEOUT_S = float(os.environ.get("SWB_WRITE_TIMEOUT_S", "60"))
POOL_TIMEOUT_S = float(os.environ.get("SWB_POOL_TIMEOUT_S", "30"))
LOCAL_READ_TIMEOUT_S = float(os.environ.get("SWB_LOCAL_READ_TIMEOUT_S", "900"))
REMOTE_READ_TIMEOUT_S = float(os.environ.get("SWB_REMOTE_READ_TIMEOUT_S", "300"))
STREAM_READ_TIMEOUT_S = float(os.environ.get("SWB_STREAM_READ_TIMEOUT_S", "1800"))

LOCAL_CONCURRENCY = max(1, int(os.environ.get("SWB_LOCAL_CONCURRENCY", "1")))
REMOTE_CONCURRENCY = max(1, int(os.environ.get("SWB_REMOTE_CONCURRENCY", "4")))

_LOCAL_TOOL_REGISTRY = None
PROFILE_CARDS_ENABLED = os.environ.get("SWB_PROFILE_CARDS_ENABLED", "1").strip() not in ("0", "false", "no")
SEMANTIC_PRUNE_ENABLED = os.environ.get("SWB_SEMANTIC_PRUNE_ENABLED", "1").strip() not in ("0", "false", "no")
SEMANTIC_TOP_K = max(2, int(os.environ.get("SWB_SEMANTIC_TOP_K", "8")))
SEMANTIC_MAX_CANDIDATES = max(4, int(os.environ.get("SWB_SEMANTIC_MAX_CANDIDATES", "24")))
SEMANTIC_EMBED_TIMEOUT_S = float(os.environ.get("SWB_SEMANTIC_EMBED_TIMEOUT_S", "4"))
REASONING_MODE = os.environ.get("SWB_REASONING_MODE", "hybrid").strip().lower()
LEXICAL_ENABLED = os.environ.get("SWB_LEXICAL_ENABLED", "1").strip() not in ("0", "false", "no")
DECOMPOSE_ENABLED = os.environ.get("SWB_DECOMPOSE_ENABLED", "1").strip() not in ("0", "false", "no")
ANSWERABILITY_GATE_ENABLED = os.environ.get("SWB_ANSWERABILITY_GATE_ENABLED", "1").strip() not in ("0", "false", "no")
ANSWERABILITY_MIN_SCORE = float(os.environ.get("SWB_ANSWERABILITY_MIN_SCORE", "0.28"))
LOOP_DETECT_ENABLED = os.environ.get("SWB_LOOP_DETECT_ENABLED", "1").strip() not in ("0", "false", "no")
LOOP_DETECT_WINDOW = max(2, int(os.environ.get("SWB_LOOP_DETECT_WINDOW", "3")))
LOOP_DETECT_THRESHOLD = float(os.environ.get("SWB_LOOP_DETECT_THRESHOLD", "0.72"))
LOOP_DETECT_LOG_PATH = os.environ.get("SWB_LOOP_DETECT_LOG_PATH", "/var/log/nixos-ai-stack/loop-events.jsonl").strip()

REMOTE_MODEL_ALIASES_ENABLED = os.environ.get("SWB_REMOTE_MODEL_ALIASES_ENABLED", "1").strip() not in ("0", "false", "no")
REMOTE_MODEL_ALIAS_GEMINI = os.environ.get("SWB_REMOTE_MODEL_ALIAS_GEMINI", "").strip()
REMOTE_MODEL_ALIAS_FREE = os.environ.get("SWB_REMOTE_MODEL_ALIAS_FREE", "").strip()
REMOTE_MODEL_ALIAS_CODING = os.environ.get("SWB_REMOTE_MODEL_ALIAS_CODING", "").strip()
REMOTE_MODEL_ALIAS_REASONING = os.environ.get("SWB_REMOTE_MODEL_ALIAS_REASONING", "").strip()
REMOTE_MODEL_ALIAS_TOOL_CALLING = os.environ.get("SWB_REMOTE_MODEL_ALIAS_TOOL_CALLING", "").strip()

REMOTE_DAILY_TOKEN_CAP = max(0, int(os.environ.get("SWB_REMOTE_DAILY_TOKEN_CAP", "0")))
REMOTE_BUDGET_FALLBACK_LOCAL = os.environ.get("SWB_REMOTE_BUDGET_FALLBACK_LOCAL", "1").strip() not in ("0", "false", "no")
REMOTE_BUDGET_STATE_PATH = os.environ.get("SWB_REMOTE_BUDGET_STATE_PATH", "").strip()

HINTS_TIMEOUT_S = float(os.environ.get("SWB_HINTS_TIMEOUT_S", "3.0"))
LOCAL_BUSY_WARN_S = float(os.environ.get("SWB_LOCAL_BUSY_WARN_S", "30"))
STARTUP_PREFIX_WARM_ENABLED = os.environ.get("SWB_STARTUP_PREFIX_WARM_ENABLED", "1").strip().lower() not in {"0", "false", "no"}

HYBRID_API_KEY = ""
_hybrid_key_file = os.environ.get("HYBRID_API_KEY_FILE", "").strip()
if _hybrid_key_file:
    try:
        with open(_hybrid_key_file) as _kf:
            HYBRID_API_KEY = _kf.read().strip()
    except OSError:
        pass

if not REMOTE_API_KEY and REMOTE_API_KEY_FILE:
    try:
        with open(REMOTE_API_KEY_FILE, "r", encoding="utf-8") as handle:
            REMOTE_API_KEY = handle.read().strip()
    except OSError:
        pass

if LOCAL_AGENTS_PATH and LOCAL_AGENTS_PATH not in sys.path:
    sys.path.insert(0, LOCAL_AGENTS_PATH)

app = FastAPI(title="AI Switchboard")
_local_sem = None
_remote_sem = None
_local_active_request = None
_local_last_completion = None
# Routing decision ring buffer — last 500 chat/completions decisions (local vs remote).
# Backed by routing-decisions.jsonl for persistence across restarts.
# Exposed via /health as routing_stats for dashboard routing panel.
_ROUTING_RING_MAXLEN = 500
_routing_ring: collections.deque = collections.deque(maxlen=_ROUTING_RING_MAXLEN)
_routing_log_lock = threading.Lock()
# Resolved at startup (see _routing_log_init).
_ROUTING_LOG_PATH: pathlib.Path | None = None
_hints_client: httpx.AsyncClient | None = None
_embed_client: httpx.AsyncClient | None = None
_local_health_client: httpx.AsyncClient | None = None

# --- Utility Functions ---

def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9_./-]+", (text or "").lower()) if len(t) >= 2]

def _extract_content_text(message: dict) -> str:
    content = message.get("content", "")
    if isinstance(content, list):
        return " ".join(
            str(part.get("text", "")) if isinstance(part, dict) else str(part)
            for part in content
        )
    return str(content)

def _estimate_tokens(text: str) -> int:
    text = str(text or "")
    word_estimate = int(len(text.split()) * 1.3)
    char_estimate = int((len(text) + 3) / 4)
    return max(1, word_estimate, char_estimate)

def _estimate_messages_tokens(messages: list) -> int:
    total = 0
    for m in messages:
        if not isinstance(m, dict):
            continue
        total += _estimate_tokens(_extract_content_text(m))
    return total

def _estimate_payload_tokens(payload: dict | None) -> int:
    if not isinstance(payload, dict):
        return 0
    if isinstance(payload.get("messages"), list):
        return _estimate_messages_tokens(payload.get("messages", []))
    if isinstance(payload.get("input"), list):
        return _estimate_messages_tokens(payload.get("input", []))
    if "prompt" in payload:
        return _estimate_tokens(str(payload.get("prompt", "")))
    return 0

def _text_similarity(a: str, b: str) -> float:
    ta = set(_tokenize(a.lower()))
    tb = set(_tokenize(b.lower()))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))

async def _get_semantic_similarity(a: str, b: str) -> float:
    if not EMBEDDING_URL or not a.strip() or not b.strip() or _embed_client is None:
        return 0.0
    try:
        payload = {"model": "semantic-similarity", "input": [a[:2000], b[:2000]]}
        resp = await _embed_client.post(f"{EMBEDDING_URL}/v1/embeddings", json=payload)
        if resp.status_code != 200:
            return 0.0
        data = resp.json()
        rows = data.get("data", [])
        if len(rows) < 2:
            return 0.0
        v1, v2 = rows[0].get("embedding", []), rows[1].get("embedding", [])
        if not v1 or not v2:
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(v1, v2))
        n1, n2 = math.sqrt(sum(float(x)**2 for x in v1)), math.sqrt(sum(float(y)**2 for y in v2))
        return max(0.0, min(1.0, dot / (n1 * n2)))
    except Exception:
        return 0.0

def _detect_tool_loop(messages: list) -> bool:
    tool_calls = []
    for m in reversed(messages):
        if not isinstance(m, dict):
            continue
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m["tool_calls"]:
                func = tc.get("function", {})
                tool_calls.append((func.get("name"), func.get("arguments")))
        if len(tool_calls) >= 4:
            break
    if len(tool_calls) < 2:
        return False
    return tool_calls[0] == tool_calls[1]

async def _detect_loop(messages: list) -> str | None:
    if not LOOP_DETECT_ENABLED or not isinstance(messages, list):
        return None
    assistant_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "assistant"]
    if len(assistant_msgs) < 2:
        return None
    if _detect_tool_loop(messages):
        return (
            "[loop-guard] IDENTICAL TOOL CALL DETECTED — STOP planning. "
            "Act immediately: issue a DIFFERENT tool call or provide a direct answer RIGHT NOW."
        )
    texts = [_extract_content_text(m) for m in assistant_msgs[-LOOP_DETECT_WINDOW:]]
    if len(texts) < 2:
        return None
    pairs = [(texts[i], texts[j]) for i in range(len(texts)) for j in range(i + 1, len(texts))]
    avg_jaccard = sum(_text_similarity(a, b) for a, b in pairs) / len(pairs)
    if avg_jaccard >= LOOP_DETECT_THRESHOLD:
        return (
            "[loop-guard] Repetitive reasoning detected — your last "
            f"{len(texts)} responses are {avg_jaccard:.0%} similar. "
            "STOP planning. Act immediately: issue your tool call or "
            "provide a direct answer RIGHT NOW. "
            "Do NOT restate intentions or add self-correction comments."
        )
    if avg_jaccard >= 0.5 and EMBEDDING_URL:
        sim = await _get_semantic_similarity(texts[-1], texts[-2])
        if sim >= 0.85:
            return (
                "[loop-guard] Semantic loop detected (similarity={sim:.2f}). "
                "STOP repeating yourself. Provide a direct answer or a new tool call."
            )
    return None

def _log_loop_event(profile: str, similarity: float, window_size: int) -> None:
    try:
        record = json.dumps({
            "event": "loop_detected",
            "ts": time.time(),
            "profile": profile,
            "similarity": round(similarity, 3),
            "window": window_size,
        })
        with open(LOOP_DETECT_LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(record + "\n")
    except Exception:
        pass

# --- Helper Functions from Nix Script ---

def _load_local_tool_registry():
    global _LOCAL_TOOL_REGISTRY
    if _LOCAL_TOOL_REGISTRY is not None:
        return _LOCAL_TOOL_REGISTRY
    try:
        from tool_registry import get_registry, ToolCall
        from builtin_tools.ai_coordination import register_ai_coordination_tools
        from builtin_tools.computer_use import register_computer_use_tools
        from builtin_tools.file_operations import register_file_tools
        from builtin_tools.git_tools import register_git_tools
        from builtin_tools.shell_tools import register_shell_tools
    except Exception as exc:
        raise RuntimeError(f"failed to import local agent tooling from {LOCAL_AGENTS_PATH}: {exc}") from exc

    registry = get_registry()
    if not registry.tools:
        register_file_tools(registry)
        register_shell_tools(registry)
        register_git_tools(registry)
        register_ai_coordination_tools(registry)
        register_computer_use_tools(registry)
    _LOCAL_TOOL_REGISTRY = (registry, ToolCall)
    return _LOCAL_TOOL_REGISTRY

def _tool_name(tool: dict) -> str:
    if not isinstance(tool, dict):
        return ""
    if tool.get("type") == "function" and isinstance(tool.get("function"), dict):
        return str(tool["function"].get("name", "")).strip()
    return str(tool.get("name", "")).strip()

def _tool_payload_from_schema(schema: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": schema.get("name", ""),
            "description": schema.get("description", ""),
            "parameters": schema.get("parameters", {"type": "object", "properties": {}}),
        },
    }

# Tool working-set bundles. These are intentionally smaller than the full
# built-in registry so a task leases only the schemas it can plausibly use.
VIRTUAL_TOOL_LEASE_NAME = "lease_tools"

_TOOL_BUNDLES = {
    "conversational": frozenset(),
    "git": frozenset({VIRTUAL_TOOL_LEASE_NAME, "git_status", "git_diff", "run_command"}),
    "search": frozenset({VIRTUAL_TOOL_LEASE_NAME, "search_files", "read_file", "list_files"}),
    "sys_ops": frozenset({VIRTUAL_TOOL_LEASE_NAME, "check_service", "get_system_info", "run_command"}),
    "file_edit": frozenset({
        VIRTUAL_TOOL_LEASE_NAME,
        "search_files",
        "read_file",
        "write_file",
        "run_command",
        "git_status",
        "validate_before_commit",
    }),
    "harness_analysis": frozenset({
        VIRTUAL_TOOL_LEASE_NAME,
        "get_hint",
        "query_context",
        "harness_health",
        "get_working_memory",
        "run_command",
        "search_files",
        "read_file",
    }),
    # Composite bundle for multi-step dev tasks: research + read + edit + validate + commit
    # Avoids bundle-switch lease calls that burn tool budget mid-task.
    "harness_dev": frozenset({
        VIRTUAL_TOOL_LEASE_NAME,
        "get_hint",
        "query_context",
        "harness_health",
        "get_working_memory",
        "search_files",
        "read_file",
        "list_files",
        "write_file",
        "run_command",
        "git_status",
        "git_diff",
        "validate_before_commit",
    }),
    "harness_control": frozenset({
        VIRTUAL_TOOL_LEASE_NAME,
        "harness_health",
        "get_prsi_pending",
        "prsi_orchestrate",
        "query_aidb",
    }),
    "agent_mesh": frozenset({
        VIRTUAL_TOOL_LEASE_NAME,
        "mesh_discovery",
        "recommend_agent_for_task",
        "collective_memory_search",
        "delegate_to_remote",
    }),
    "memory": frozenset({
        VIRTUAL_TOOL_LEASE_NAME,
        "get_hint",
        "query_context",
        "store_memory",
        "get_working_memory",
        "collective_memory_search",
    }),
    "computer_use": frozenset({VIRTUAL_TOOL_LEASE_NAME, "screenshot", "get_screen_size"}),
    "default": frozenset({VIRTUAL_TOOL_LEASE_NAME, "get_hint", "query_context", "harness_health"}),
}

_TOOL_LEASE_PRIORITY = {
    VIRTUAL_TOOL_LEASE_NAME: 5,
    "get_hint": 10,
    "harness_health": 15,
    "query_context": 20,
    "get_working_memory": 25,
    "mesh_discovery": 30,
    "check_service": 35,
    "get_system_info": 40,
    "search_files": 50,
    "read_file": 60,
    "list_files": 70,
    "run_command": 80,
    "git_status": 90,
    "git_diff": 100,
    "validate_before_commit": 110,
    "write_file": 120,
    "store_memory": 130,
    "screenshot": 140,
    "get_screen_size": 150,
    "query_aidb": 160,
    "collective_memory_search": 170,
    "recommend_agent_for_task": 180,
    "get_prsi_pending": 190,
    "prsi_orchestrate": 200,
    "delegate_to_remote": 210,
}


def _virtual_lease_tools_payload() -> dict:
    return {
        "type": "function",
        "function": {
            "name": VIRTUAL_TOOL_LEASE_NAME,
            "description": (
                "Swap the active local tool lease for the next step without loading the full tool registry. "
                "Use this when the current task needs a different tool bundle."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string",
                        "description": "Intent bundle to lease.",
                        "enum": sorted(_TOOL_BUNDLES.keys()),
                    },
                    "tools": {
                        "type": "array",
                        "description": "Optional explicit built-in tool names to lease instead of an intent bundle.",
                        "items": {"type": "string"},
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason the active tool set needs to change.",
                    },
                },
            },
        },
    }


def _local_tool_schema_catalog(registry) -> dict[str, dict]:
    available = {
        tool.name: _tool_payload_from_schema(tool.to_json_schema())
        for tool in registry.list_tools()
    }
    available[VIRTUAL_TOOL_LEASE_NAME] = _virtual_lease_tools_payload()
    return available


def _latest_user_text(messages: list) -> str:
    if not isinstance(messages, list):
        return ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        text = _extract_content_text(message).strip()
        if text:
            return text
    return ""


def _classify_tool_intent(messages: list) -> str:
    text = _latest_user_text(messages).lower()
    if not text:
        return "default"
    compact = re.sub(r"\s+", " ", text).strip()
    words = set(_tokenize(compact))
    conversational_exact = {
        "hi",
        "hello",
        "hey",
        "how are you",
        "how are you today",
        "thanks",
        "thank you",
        "ok",
        "okay",
        "yes",
        "no",
    }
    if compact in conversational_exact:
        return "conversational"
    # Compound dev task: self-improvement, slices, or edit+commit in one request → composite bundle.
    # Checked before the short-message conversational guard so that "hi" substring in e.g. "this"
    # doesn't shadow legitimate dev tasks with few tokens.
    _harness_dev_direct = {"improvement", "improvements", "slice", "slices", "self-improve", "self_improve", "self-improvement", "self_improvement"}
    if any(t in words for t in _harness_dev_direct):
        return "harness_dev"
    if (any(t in words for t in {"fix", "implement", "edit", "refactor", "patch", "create", "write"}) and
            any(t in words for t in {"commit", "validate", "verify", "test", "push"})):
        return "harness_dev"
    if len(words) <= 8 and any(greet in compact for greet in ("hello", "hi", "hey", "how are you", "who are you")):
        return "conversational"
    if any(token in words for token in {"git", "commit", "diff", "branch", "staged", "unstaged", "status"}):
        return "git"
    if any(token in words for token in {"systemctl", "service", "journalctl", "health", "restart", "deploy", "rebuild", "nixos", "gpu", "memory", "cpu"}):
        return "sys_ops"
    if any(token in words for token in {"search", "grep", "find", "where", "locate", "read", "file", "files", "codebase"}):
        return "search"
    if any(token in words for token in {"fix", "implement", "edit", "patch", "change", "update", "refactor", "test", "validate"}):
        return "file_edit"
    if any(token in words for token in {"harness", "analysis", "analyze", "assessment", "primer", "workflow", "phase", "agent", "agents", "context", "tools"}):
        return "harness_analysis"
    if any(token in words for token in {"memory", "remember", "recall", "store"}):
        return "memory"
    if any(token in words for token in {"screenshot", "screen", "click", "mouse", "keyboard"}):
        return "computer_use"
    return "default"


def _tool_working_set_meta(intent: str, selected_names: set[str], available_count: int, explicit: bool) -> dict:
    return {
        "enabled": bool(TOOL_WORKING_SET_ENABLED),
        "intent": intent,
        "explicit": bool(explicit),
        "active_schema_limit": int(ACTIVE_TOOL_SCHEMA_LIMIT),
        "selected_count": len(selected_names),
        "available_count": int(available_count),
        "selected_tools": sorted(selected_names),
        "evicted_count": max(0, int(available_count) - len(selected_names)),
    }

def _cap_active_tool_names(selected_names: set[str]) -> set[str]:
    if len(selected_names) <= ACTIVE_TOOL_SCHEMA_LIMIT:
        return set(selected_names)
    ordered = sorted(
        selected_names,
        key=lambda name: (_TOOL_LEASE_PRIORITY.get(name, 1000), name),
    )
    return set(ordered[:ACTIVE_TOOL_SCHEMA_LIMIT])


def _resolve_tool_lease(arguments: dict, available_names: set[str], current_allowed: set[str]) -> tuple[set[str], dict]:
    """Resolve a virtual lease_tools request into the next active tool set."""
    current = set(current_allowed or set())
    intent = str((arguments or {}).get("intent") or "").strip()
    explicit_tools = (arguments or {}).get("tools")
    reason = str((arguments or {}).get("reason") or "").strip()
    if isinstance(explicit_tools, list) and explicit_tools:
        requested = {
            str(name).strip()
            for name in explicit_tools
            if str(name or "").strip()
        }
        unsupported = sorted(name for name in requested if name not in available_names)
        if unsupported:
            return current, {
                "tool": VIRTUAL_TOOL_LEASE_NAME,
                "status": "error",
                "error": "unsupported requested tool(s): " + ", ".join(unsupported),
                "active_tools": sorted(current),
            }
        selected = requested
        lease_intent = "explicit"
    else:
        lease_intent = intent if intent in _TOOL_BUNDLES else "default"
        selected = set(_TOOL_BUNDLES.get(lease_intent, _TOOL_BUNDLES["default"]))
        selected = {name for name in selected if name in available_names}
    if selected and lease_intent != "conversational":
        selected.add(VIRTUAL_TOOL_LEASE_NAME)
    selected = _cap_active_tool_names(selected)
    evicted = sorted(current - selected)
    added = sorted(selected - current)
    return selected, {
        "tool": VIRTUAL_TOOL_LEASE_NAME,
        "status": "ok",
        "intent": lease_intent,
        "reason": reason,
        "active_schema_limit": int(ACTIVE_TOOL_SCHEMA_LIMIT),
        "active_tools": sorted(selected),
        "added_tools": added,
        "evicted_tools": evicted,
    }


def _select_auto_tool_names(messages: list, available_names: set[str]) -> tuple[str, set[str]]:
    if not TOOL_WORKING_SET_ENABLED:
        legacy = {"run_command", "read_file", "search_files", "git_status", "query_context", "get_hint"}
        return "legacy-core", {name for name in legacy if name in available_names}
    intent = _classify_tool_intent(messages)
    selected = set(_TOOL_BUNDLES.get(intent, _TOOL_BUNDLES["default"]))
    selected = {name for name in selected if name in available_names}
    if intent != "conversational" and not selected:
        selected = {name for name in _TOOL_BUNDLES["default"] if name in available_names}
    selected = _cap_active_tool_names(selected)
    return intent, selected


def _normalize_local_tools(requested_tools, messages=None):
    registry, _tool_call_cls = _load_local_tool_registry()
    available = _local_tool_schema_catalog(registry)
    available_names = set(available)
    if isinstance(requested_tools, list) and requested_tools:
        if any((isinstance(tool, str) and tool.strip() == "*") for tool in requested_tools):
            selected_names = set(available_names)
            selected = [available[name] for name in sorted(selected_names)]
            return selected, selected_names, _tool_working_set_meta("explicit-all", selected_names, len(available), True)
        selected = []
        unsupported = []
        seen = set()
        for tool in requested_tools:
            name = _tool_name(tool)
            if not name:
                continue
            if name not in available:
                unsupported.append(name)
                continue
            if name in seen:
                continue
            selected.append(available[name])
            seen.add(name)
        if unsupported:
            raise ValueError(
                "local-tool-calling only supports built-in server tools; unsupported: "
                + ", ".join(sorted(set(unsupported)))
            )
        if not selected:
            raise ValueError("local-tool-calling did not receive any executable built-in tools")
        return selected, set(seen), _tool_working_set_meta("explicit", set(seen), len(available), True)
    # No explicit tool list → hot-load only the bundle for the current user turn.
    intent, selected_names = _select_auto_tool_names(messages or [], available_names)
    selected = [available[name] for name in sorted(selected_names)]
    return selected, selected_names, _tool_working_set_meta(intent, selected_names, len(available), False)

def _normalize_tool_choice(tool_choice, allowed_names):
    if tool_choice in (None, "", False):
        return "auto"
    if isinstance(tool_choice, str):
        lowered = tool_choice.strip().lower()
        if lowered in {"auto", "none", "required"}:
            return lowered
        return "auto"
    if isinstance(tool_choice, dict):
        function_name = _tool_name(tool_choice)
        if function_name and function_name not in allowed_names:
            raise ValueError(f"tool_choice requested unsupported local tool: {function_name}")
        return tool_choice
    return "auto"


def _filter_remote_tools_for_working_set(payload: dict, profile: str) -> tuple[dict, dict | None]:
    if (
        not REMOTE_TOOL_WORKING_SET_ENABLED
        or profile != "remote-tool-calling"
        or not isinstance(payload, dict)
        or not isinstance(payload.get("tools"), list)
        or not payload.get("tools")
    ):
        return payload, None
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload, None
    intent = _classify_tool_intent(messages)
    allowed_names = set(_TOOL_BUNDLES.get(intent, _TOOL_BUNDLES["default"]))
    before_tools = list(payload.get("tools") or [])
    if intent == "conversational":
        updated = dict(payload)
        updated.pop("tools", None)
        updated["tool_choice"] = "none"
        return updated, {
            "enabled": True,
            "intent": intent,
            "explicit": False,
            "selected_count": 0,
            "available_count": len(before_tools),
            "selected_tools": [],
            "evicted_count": len(before_tools),
            "scope": "remote-explicit",
        }
    selected = [tool for tool in before_tools if _tool_name(tool) in allowed_names]
    if not selected:
        return payload, {
            "enabled": True,
            "intent": intent,
            "explicit": True,
            "selected_count": len(before_tools),
            "available_count": len(before_tools),
            "selected_tools": [_tool_name(tool) for tool in before_tools if _tool_name(tool)],
            "evicted_count": 0,
            "scope": "remote-explicit-no-match",
        }
    updated = dict(payload)
    updated["tools"] = selected
    return updated, {
        "enabled": True,
        "intent": intent,
        "explicit": False,
        "selected_count": len(selected),
        "available_count": len(before_tools),
        "selected_tools": [_tool_name(tool) for tool in selected if _tool_name(tool)],
        "evicted_count": max(0, len(before_tools) - len(selected)),
        "scope": "remote-explicit",
    }


def _json_safe_preview(value, max_chars: int) -> str:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=True, sort_keys=True)
    else:
        text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= max_chars:
        return text
    return text[: max(0, max_chars - 3)].rstrip() + "..."


def _canonical_tool_arguments(raw_arguments) -> str:
    try:
        parsed = json.loads(raw_arguments) if isinstance(raw_arguments, str) else raw_arguments
        return json.dumps(parsed or {}, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        return str(raw_arguments or "")


def _tool_result_cache_key(tool_name: str, raw_arguments) -> str:
    base = json.dumps(
        {
            "tool": str(tool_name or ""),
            "arguments": _canonical_tool_arguments(raw_arguments),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def _context_gc_empty_stats() -> dict:
    return {
        "enabled": bool(CONTEXT_OUTPUT_GC_ENABLED),
        "artifacts_written": 0,
        "raw_chars_pruned": 0,
        "duplicate_tool_calls": 0,
        "tool_observations_compacted": 0,
    }


def _tool_result_summary(tool_name: str, result_text: str, max_chars: int) -> dict:
    summary = {
        "tool": tool_name,
        "status": "compacted",
        "preview": _json_safe_preview(result_text, max_chars),
    }
    try:
        parsed = json.loads(result_text)
    except Exception:
        return summary
    if isinstance(parsed, dict):
        summary["status"] = parsed.get("status", summary["status"])
        if parsed.get("error"):
            summary["error"] = _json_safe_preview(parsed.get("error"), max_chars)
        if "result" in parsed:
            result = parsed.get("result")
            summary["result_type"] = type(result).__name__
            if isinstance(result, (list, tuple, dict, str)):
                summary["result_size"] = len(result)
            summary["preview"] = _json_safe_preview(result, max_chars)
    return summary


def _compact_tool_result_if_needed(tool_name: str, tool_call_id: str, result_text: str, stats: dict) -> str:
    raw = str(result_text or "")
    if not CONTEXT_OUTPUT_GC_ENABLED or len(raw) < CONTEXT_OUTPUT_GC_MIN_CHARS:
        return raw
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
    artifact_dir = pathlib.Path(CONTEXT_ARTIFACT_DIR).expanduser()
    try:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"{int(time.time())}-{tool_name}-{digest[:12]}.json"
        artifact_payload = {
            "created_at": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "tool": tool_name,
            "tool_call_id": tool_call_id,
            "sha256": digest,
            "raw_chars": len(raw),
            "content": raw,
        }
        artifact_path.write_text(json.dumps(artifact_payload, ensure_ascii=True, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"[switchboard] context_output_gc_failed tool={tool_name} error={exc}", file=sys.stderr)
        return raw
    summary = _tool_result_summary(tool_name, raw, CONTEXT_OUTPUT_GC_SUMMARY_CHARS)
    summary.update({
        "artifact_path": str(artifact_path),
        "sha256": digest,
        "raw_chars": len(raw),
        "raw_output_compacted": True,
    })
    compact = json.dumps(summary, ensure_ascii=True, sort_keys=True)
    stats["artifacts_written"] = int(stats.get("artifacts_written", 0) or 0) + 1
    stats["raw_chars_pruned"] = int(stats.get("raw_chars_pruned", 0) or 0) + max(0, len(raw) - len(compact))
    stats["tool_observations_compacted"] = int(stats.get("tool_observations_compacted", 0) or 0) + 1
    return compact


def _local_tool_limit_fallback(body: dict, tool_calls_used: int) -> dict:
    return {
        "id": body.get("id", f"local-tool-limit-{time.time_ns()}"),
        "object": "chat.completion",
        "created": int(time.time()),
        "model": body.get("model", "local"),
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": (
                    f"Local tool-call limit reached after {tool_calls_used} calls. "
                    "I stopped to avoid an execution loop; any completed tool outputs or files remain available. "
                    "Continue with a narrower request or rerun with a higher --max-tools value if more tool work is intentional."
                ),
            },
            "finish_reason": "tool_calls_exhausted",
        }],
        "usage": body.get("usage", {}),
        "local_tool_budget_exhausted": True,
        "local_tool_finalization": "fallback",
    }


async def _finalize_after_local_tool_limit(
    client: httpx.AsyncClient,
    request_payload: dict,
    body: dict,
    messages: list,
    tool_calls_used: int,
    max_tool_calls: int,
) -> dict:
    """Force a final, tool-free answer after local tool budget exhaustion."""
    final_messages = list(messages)
    final_messages.append({
        "role": "user",
        "content": (
            f"You have used the local tool budget ({tool_calls_used}/{max_tool_calls}). "
            "Stop calling tools. Produce a complete final answer now from the completed tool outputs. "
            "Prioritize the user's requested analysis and recommendations over explaining the tool budget. "
            "Mention any artifact paths that were created or inspected. If evidence is incomplete, state the gap and the next narrow check. "
            "Do not stop mid-sentence."
        ),
    })
    final_payload = {
        key: value
        for key, value in request_payload.items()
        if key not in {"tools", "tool_choice", "max_tool_calls"}
    }
    final_payload["messages"] = final_messages
    final_payload["stream"] = False
    final_payload["max_tokens"] = max(768, min(int(final_payload.get("max_tokens") or 1536), 2048))
    try:
        upstream = await client.post(
            f"{LLAMA_URL}/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            json=final_payload,
        )
        final_body = upstream.json()
        choices = final_body.get("choices", []) if isinstance(final_body, dict) else []
        content = ""
        if choices and isinstance(choices[0], dict):
            content = str((choices[0].get("message") or {}).get("content") or "").strip()
        if upstream.status_code < 400 and content:
            final_body["local_tool_budget_exhausted"] = True
            final_body["local_tool_finalization"] = "forced_tool_free"
            return final_body
    except Exception as exc:
        print(f"[switchboard] local_tool_limit_finalization_failed: {exc}", file=sys.stderr)
    return _local_tool_limit_fallback(body, tool_calls_used)


async def _execute_local_tool_calling(payload: dict, run_id: str = "unknown-run") -> tuple[dict, int]:
    registry, tool_call_cls = _load_local_tool_registry()
    messages = list(payload.get("messages") or [])
    if not messages:
        raise ValueError("chat/completions requires messages for local-tool-calling")
    available_schemas = _local_tool_schema_catalog(registry)
    available_names = set(available_schemas)
    tools_payload, allowed_names, working_set = _normalize_local_tools(payload.get("tools"), messages)
    tool_choice = _normalize_tool_choice(payload.get("tool_choice"), allowed_names)

    requested_limit = payload.get("max_tool_calls", LOCAL_TOOL_CALL_LIMIT)
    try:
        max_tool_calls = int(requested_limit)
    except (TypeError, ValueError):
        max_tool_calls = LOCAL_TOOL_CALL_LIMIT
    max_tool_calls = max(1, min(max_tool_calls, LOCAL_TOOL_CALL_LIMIT))
    tool_calls_used = 0
    tool_result_cache = {}
    context_gc = _context_gc_empty_stats()
    lease_events = []
    request_payload = dict(payload)
    request_payload["messages"] = messages
    if tools_payload:
        request_payload["tools"] = tools_payload
        request_payload["tool_choice"] = tool_choice
    else:
        request_payload.pop("tools", None)
        request_payload["tool_choice"] = "none"
    request_payload["stream"] = False

    async with httpx.AsyncClient(timeout=_timeout_for("local", False)) as client:
        if not tools_payload:
            try:
                upstream = await _call_upstream_with_resilience(
                    client=client,
                    method="POST",
                    url=f"{LLAMA_URL}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json_body={k: v for k, v in request_payload.items() if k != "tool_choice"},
                    service_name="llama",
                )
            except CircuitBreakerOpenError as exc:
                raise RuntimeError(f"Circuit breaker is OPEN: {exc}")

            body = upstream.json()
            if upstream.status_code >= 400:
                message = body.get("error", {}).get("message") if isinstance(body, dict) else str(body)
                raise RuntimeError(f"local llama.cpp tool-free step failed: {message or upstream.text}")
            if isinstance(body, dict):
                body["tool_working_set"] = working_set
                body["context_output_gc"] = context_gc

                # Phase 149: Record safe reasoning-observed summaries only.
                choices = body.get("choices", [])
                message_obj = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
                content = message_obj.get("content", "") or ""
                clean_content = await _emit_reasoning_summary_events(run_id, content)
                if clean_content != content and choices and isinstance(choices[0], dict):
                    choices[0].setdefault("message", {})["content"] = clean_content

            return body, tool_calls_used
        while True:
            try:
                upstream = await _call_upstream_with_resilience(
                    client=client,
                    method="POST",
                    url=f"{LLAMA_URL}/v1/chat/completions",
                    headers={"Content-Type": "application/json"},
                    json_body=request_payload,
                    service_name="llama",
                )
            except CircuitBreakerOpenError as exc:
                raise RuntimeError(f"Circuit breaker is OPEN: {exc}")

            body = upstream.json()
            if upstream.status_code >= 400:
                message = body.get("error", {}).get("message") if isinstance(body, dict) else str(body)
                raise RuntimeError(f"local llama.cpp tool step failed: {message or upstream.text}")
            choices = body.get("choices", []) if isinstance(body, dict) else []
            if not choices:
                raise RuntimeError("local llama.cpp returned no choices during tool execution")
            message_obj = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
            content = message_obj.get("content", "") or ""
            content = await _emit_reasoning_summary_events(run_id, content)
            message_obj["content"] = content

            tool_calls = message_obj.get("tool_calls") or []
            if not tool_calls:
                if isinstance(body, dict):
                    body["tool_working_set"] = working_set
                    body["context_output_gc"] = context_gc
                return body, tool_calls_used

            messages.append({
                "role": "assistant",
                "content": content,
                "tool_calls": tool_calls,
            })

            for tool_index, tool_call in enumerate(tool_calls):
                if tool_calls_used >= max_tool_calls:
                    for skipped_call in tool_calls[tool_index:]:
                        skipped_id = str(skipped_call.get("id", "")).strip() or hashlib.md5(
                            f"skipped:{time.time()}".encode("utf-8")
                        ).hexdigest()[:16]
                        messages.append({
                            "role": "tool",
                            "tool_call_id": skipped_id,
                            "content": json.dumps({
                                "status": "skipped",
                                "reason": "local_tool_call_limit_exhausted",
                                "tool_calls_used": tool_calls_used,
                                "max_tool_calls": max_tool_calls,
                            }),
                        })
                    final_body = await _finalize_after_local_tool_limit(
                        client, request_payload, body, messages, tool_calls_used, max_tool_calls
                    )
                    if isinstance(final_body, dict):
                        final_body["tool_working_set"] = working_set
                        final_body["context_output_gc"] = context_gc
                    return final_body, tool_calls_used
                function_payload = tool_call.get("function", {}) if isinstance(tool_call, dict) else {}
                tool_name = str(function_payload.get("name", "")).strip()
                raw_arguments = function_payload.get("arguments", "{}")
                tool_call_id = str(tool_call.get("id", "")).strip() or hashlib.md5(
                    f"{tool_name}:{time.time()}".encode("utf-8")
                ).hexdigest()[:16]
                if tool_name not in allowed_names:
                    tool_result_text = json.dumps({
                        "tool": tool_name,
                        "status": "error",
                        "error": f"unsupported local tool: {tool_name}",
                    })
                elif tool_name == VIRTUAL_TOOL_LEASE_NAME:
                    try:
                        arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments or {})
                    except Exception as exc:
                        tool_result_text = json.dumps({
                            "tool": tool_name,
                            "status": "error",
                            "error": f"invalid JSON arguments: {exc}",
                            "raw_arguments": raw_arguments,
                        })
                    else:
                        next_allowed, lease_result = _resolve_tool_lease(arguments, available_names, allowed_names)
                        if lease_result.get("status") == "ok":
                            allowed_names = set(next_allowed)
                            tools_payload = [available_schemas[name] for name in sorted(allowed_names)]
                            if tools_payload:
                                request_payload["tools"] = tools_payload
                            else:
                                request_payload.pop("tools", None)
                            working_set["intent"] = f"lease:{lease_result.get('intent', 'default')}"
                            working_set["selected_count"] = len(allowed_names)
                            working_set["selected_tools"] = sorted(allowed_names)
                            working_set["evicted_count"] = max(0, int(working_set.get("available_count", len(available_names))) - len(allowed_names))
                            lease_events.append(lease_result)
                            working_set["lease_count"] = len(lease_events)
                            working_set["lease_events"] = lease_events[-5:]
                        tool_result_text = json.dumps(lease_result, ensure_ascii=True, sort_keys=True)
                else:
                    cache_key = _tool_result_cache_key(tool_name, raw_arguments)
                    cached_result = tool_result_cache.get(cache_key) if TOOL_RESULT_DEDUPE_ENABLED else None
                    if cached_result is not None:
                        context_gc["duplicate_tool_calls"] = int(context_gc.get("duplicate_tool_calls", 0) or 0) + 1
                        tool_result_text = json.dumps({
                            "tool": tool_name,
                            "status": "cached",
                            "cached_from_tool_call_id": cached_result.get("tool_call_id"),
                            "result": cached_result.get("content"),
                        })
                    else:
                        try:
                            arguments = json.loads(raw_arguments) if isinstance(raw_arguments, str) else dict(raw_arguments or {})
                        except Exception as exc:
                            tool_result_text = json.dumps({
                                "tool": tool_name,
                                "status": "error",
                                "error": f"invalid JSON arguments: {exc}",
                                "raw_arguments": raw_arguments,
                            })
                        else:
                            tool_call_obj = tool_call_cls(
                                id=tool_call_id,
                                tool_name=tool_name,
                                arguments=arguments,
                                model_id=str(body.get("model", "")),
                                session_id=f"switchboard-{hashlib.md5(json.dumps(messages, default=str).encode('utf-8')).hexdigest()[:12]}",
                            )
                            tool_result = await registry.execute_tool_call(tool_call_obj)
                            tool_result_text = registry.format_tool_result(tool_result)
                        tool_result_text = _compact_tool_result_if_needed(tool_name, tool_call_id, tool_result_text, context_gc)
                        if TOOL_RESULT_DEDUPE_ENABLED:
                            tool_result_cache[cache_key] = {
                                "tool_call_id": tool_call_id,
                                "content": tool_result_text,
                            }
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": tool_result_text,
                })
                tool_calls_used += 1

            request_payload["messages"] = messages
            request_payload["tool_choice"] = "auto"

def _latest_user_excerpt(messages: list, max_chars: int = 160) -> str:
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        text = _extract_content_text(message).strip()
        if not text:
            continue
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3].rstrip() + "..."
    return ""

def _begin_local_active_request(path: str, profile: str, payload: dict | None, is_stream: bool) -> str:
    global _local_active_request
    request_id = str(time.time_ns())
    messages = payload.get("messages") if isinstance(payload, dict) else []
    if not isinstance(messages, list):
        messages = []
    metadata = {
        "id": request_id,
        "path": path,
        "profile": str(profile or "").strip(),
        "stream": bool(is_stream),
        "started_at": time.time(),
        "estimated_input_tokens": int(_estimate_payload_tokens(payload) or 0),
        "message_count": len(messages),
    }
    if isinstance(payload, dict) and payload.get("max_tokens") is not None:
        try:
            metadata["max_tokens"] = int(payload.get("max_tokens") or 0)
        except Exception:
            pass
    latest_user_excerpt = _latest_user_excerpt(messages)
    if latest_user_excerpt:
        metadata["latest_user_excerpt"] = latest_user_excerpt
    _local_active_request = metadata
    return request_id

def _clear_local_active_request(request_id: str) -> None:
    global _local_active_request
    if not isinstance(_local_active_request, dict):
        return
    if str(_local_active_request.get("id") or "") != str(request_id or ""):
        return
    _local_active_request = None

def _local_active_request_snapshot() -> dict | None:
    if not isinstance(_local_active_request, dict):
        return None
    snapshot = dict(_local_active_request)
    started_at = float(snapshot.get("started_at") or 0.0)
    duration_s = max(0.0, time.time() - started_at) if started_at > 0 else 0.0
    snapshot["duration_s"] = round(duration_s, 3)
    snapshot["long_running"] = duration_s >= LOCAL_BUSY_WARN_S
    return snapshot

def _record_local_completion(path: str, profile: str, status_code: int, body: bytes | None) -> None:
    global _local_last_completion
    snapshot = {
        "path": str(path or "").strip(),
        "profile": str(profile or "").strip(),
        "status_code": int(status_code),
        "captured_at": time.time(),
    }
    if status_code < 200 or status_code >= 300 or not body:
        _local_last_completion = snapshot
        return
    try:
        payload = json.loads(body.decode("utf-8"))
    except Exception:
        _local_last_completion = snapshot
        return
    if not isinstance(payload, dict):
        _local_last_completion = snapshot
        return
    usage = payload.get("usage")
    if isinstance(usage, dict):
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            value = usage.get(key)
            if isinstance(value, (int, float)):
                snapshot[key] = int(value)
        prompt_tokens_details = usage.get("prompt_tokens_details")
        if isinstance(prompt_tokens_details, dict):
            cached_tokens = prompt_tokens_details.get("cached_tokens")
            if isinstance(cached_tokens, (int, float)):
                snapshot["prompt_tokens_details"] = {"cached_tokens": int(cached_tokens)}
    timings = payload.get("timings")
    if isinstance(timings, dict):
        summary = {}
        for key in ("prompt_n", "prompt_ms", "predicted_n", "predicted_ms"):
            value = timings.get(key)
            if isinstance(value, (int, float)):
                summary[key] = float(value) if str(key).endswith("_ms") else int(value)
        if summary:
            snapshot["timings"] = summary
    _local_last_completion = snapshot

def _local_last_completion_snapshot() -> dict | None:
    if not isinstance(_local_last_completion, dict):
        return None
    snapshot = dict(_local_last_completion)
    captured_at = float(snapshot.get("captured_at") or 0.0)
    age_s = max(0.0, time.time() - captured_at) if captured_at > 0 else 0.0
    snapshot["age_s"] = round(age_s, 3)
    return snapshot

def _local_lane_status(local_runtime: dict | None) -> str:
    if not isinstance(local_runtime, dict):
        return "unknown"
    active_request = local_runtime.get("active_request")
    if isinstance(active_request, dict) and active_request.get("long_running") is True:
        return "busy-long-running"
    if local_runtime.get("slot_busy") is True:
        return "busy"
    slot_available = local_runtime.get("slot_available")
    if isinstance(slot_available, (int, float)) and slot_available > 0:
        return "available"
    if local_runtime.get("llama_metrics_error"):
        return "degraded"
    return "unknown"

def _truncate_text_to_token_budget(text: str, max_tokens: int) -> str:
    raw = str(text or "")
    if max_tokens <= 0 or _estimate_tokens(raw) <= max_tokens:
        return raw
    max_chars = max(64, max_tokens * 4)
    if len(raw) <= max_chars:
        return raw
    if max_chars <= 80:
        return raw[:max_chars]
    head_chars = int(max_chars * 0.7)
    tail_chars = max(24, max_chars - head_chars - 18)
    return raw[:head_chars] + "\n[... trimmed ...]\n" + raw[-tail_chars:]

def _truncate_message_to_token_budget(message: dict, max_tokens: int) -> dict:
    updated = dict(message)
    updated["content"] = _truncate_text_to_token_budget(_extract_content_text(message), max_tokens)
    return updated

def _looks_like_strict_reply_only(messages: list) -> bool:
    if not isinstance(messages, list):
        return False
    latest_user = ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        latest_user = _extract_content_text(message).strip()
        if latest_user:
            break
    if not latest_user:
        return False
    lowered = latest_user.lower()
    return (
        " only" in lowered
        and len(latest_user.split()) <= 12
        and any(token in lowered for token in ("reply", "respond", "return"))
    )

def _looks_like_compact_guidance_request(messages: list) -> bool:
    if not isinstance(messages, list):
        return False
    latest_user = ""
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        latest_user = _extract_content_text(message).strip()
        if latest_user:
            break
    if not latest_user:
        return False
    lowered = latest_user.lower()
    if len(latest_user.split()) > 120:
        return False
    compact_cues = ("compact", "brief", "concise", "short")
    guidance_cues = ("next steps", "diagnosis", "diagnose", "plan", "path")
    return any(cue in lowered for cue in compact_cues) and any(cue in lowered for cue in guidance_cues)

def _decompose_query(query_text: str) -> list[str]:
    if not query_text.strip():
        return []
    if not DECOMPOSE_ENABLED:
        return [query_text]
    lowered = query_text.strip()
    parts = re.split(r"\b(?:and|then|also)\b|[,\n;]+", lowered, maxsplit=3)
    pieces = [p.strip() for p in parts if p.strip()]
    if len(pieces) <= 1:
        return [query_text]
    return [query_text] + pieces[:3]

async def _semantic_scores(candidates: list, query_text: str) -> dict[int, float]:
    if not SEMANTIC_PRUNE_ENABLED or not EMBEDDING_URL or not query_text.strip() or _embed_client is None:
        return {}
    
    breaker = LOCAL_CIRCUIT_BREAKERS.get("embedding")
    
    async def _do_embed():
        payload = {
            "model": "semantic-rerank",
            "input": [query_text] + [_extract_content_text(m)[:2000] for m in candidates],
        }
        resp = await _embed_client.post(f"{EMBEDDING_URL}/v1/embeddings", json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"Embedding failed: {resp.status_code}")
        return resp.json()

    try:
        data = await retry_with_backoff(
            breaker.call,
            _do_embed,
            max_attempts=2,
            breaker=breaker,
            retry_on_exceptions=(httpx.TimeoutException, httpx.NetworkError, RuntimeError),
        )
        
        rows = data.get("data", [])
        if len(rows) < 2:
            return {}

        qv = rows[0].get("embedding", [])
        if not isinstance(qv, list) or not qv:
            return {}

        qnorm = math.sqrt(sum(float(x) * float(x) for x in qv)) or 1.0
        scored = {}
        for idx, row in enumerate(rows[1:]):
            ev = row.get("embedding", [])
            if not isinstance(ev, list) or not ev:
                continue
            dot = sum(float(a) * float(b) for a, b in zip(qv, ev))
            enorm = math.sqrt(sum(float(x) * float(x) for x in ev)) or 1.0
            cosine = dot / (qnorm * enorm)
            scored[idx] = max(0.0, min(1.0, cosine))
        return scored
    except Exception:
        return {}

def _lexical_scores(candidates: list, query_variants: list[str]) -> dict[int, float]:
    if not LEXICAL_ENABLED or not query_variants:
        return {}
    token_sets = [set(_tokenize(q)) for q in query_variants if q.strip()]
    token_sets = [s for s in token_sets if s]
    if not token_sets:
        return {}
    scores = {}
    for idx, msg in enumerate(candidates):
        text = _extract_content_text(msg).lower()
        msg_tokens = set(_tokenize(text))
        if not msg_tokens:
            continue
        best = 0.0
        for qset in token_sets:
            overlap = len(qset.intersection(msg_tokens))
            if overlap <= 0:
                continue
            containment = overlap / max(1, len(qset))
            exact_bonus = 0.12 if any(t in text for t in list(qset)[:4]) else 0.0
            best = max(best, min(1.0, containment + exact_bonus))
        if best > 0.0:
            scores[idx] = best
    return scores

def _rrf_scores(score_maps: list[dict[int, float]]) -> dict[int, float]:
    fused = {}
    k = 50.0
    for smap in score_maps:
        ranked = sorted(smap.items(), key=lambda item: item[1], reverse=True)
        for rank, (idx, _) in enumerate(ranked, start=1):
            fused[idx] = fused.get(idx, 0.0) + (1.0 / (k + rank))
    return fused

async def _select_non_system(non_system_messages: list, query_text: str) -> tuple[list, float, str]:
    if len(non_system_messages) <= SEMANTIC_TOP_K:
        return non_system_messages, 1.0, "no-prune"
    candidates = non_system_messages[-SEMANTIC_MAX_CANDIDATES:]
    scoring_candidates = []
    scoring_index_map = []
    query_norm = query_text.strip().lower()
    for idx, msg in enumerate(candidates):
        if (
            query_norm
            and isinstance(msg, dict)
            and msg.get("role") == "user"
            and _extract_content_text(msg).strip().lower() == query_norm
        ):
            continue
        scoring_candidates.append(msg)
        scoring_index_map.append(idx)
    if not scoring_candidates:
        return candidates[-SEMANTIC_TOP_K:], 0.0, "recency-fallback"
    query_variants = _decompose_query(query_text)
    semantic_raw = await _semantic_scores(scoring_candidates, query_variants[0] if query_variants else "")
    lexical_raw = _lexical_scores(scoring_candidates, query_variants)
    semantic = {scoring_index_map[idx]: score for idx, score in semantic_raw.items() if idx < len(scoring_index_map)}
    lexical = {scoring_index_map[idx]: score for idx, score in lexical_raw.items() if idx < len(scoring_index_map)}

    mode = REASONING_MODE
    if mode not in ("semantic", "lexical", "hybrid"):
        mode = "hybrid"

    if mode == "semantic":
        combined = semantic
        best_score = max(semantic.values(), default=0.0)
    elif mode == "lexical":
        combined = lexical
        best_score = max(lexical.values(), default=0.0)
    else:
        if semantic and lexical:
            combined = _rrf_scores([semantic, lexical])
            best_score = max((0.65 * semantic.get(i, 0.0) + 0.35 * lexical.get(i, 0.0)) for i in set(semantic) | set(lexical))
        else:
            combined = semantic or lexical
            best_score = max((combined or {0: 0.0}).values())

    if not combined:
        return candidates[-SEMANTIC_TOP_K:], 0.0, "recency-fallback"

    top = {idx for idx, _ in sorted(combined.items(), key=lambda item: item[1], reverse=True)[:SEMANTIC_TOP_K]}
    for idx in range(max(0, len(candidates) - 2), len(candidates)):
        top.add(idx)
    selected = [m for idx, m in enumerate(candidates) if idx in top]
    return (selected if selected else non_system_messages), best_score, f"{mode}-rrf"

async def _trim_profile_messages(messages: list, profile: str) -> tuple[list, bool, int, int, str, float, bool]:
    if not isinstance(messages, list):
        return messages, False, 0, 0, "none", 1.0, False

    profile_settings = _profile_settings(profile)
    max_tokens = profile_settings.get("maxInputTokens")
    max_messages = profile_settings.get("maxMessages")
    if not isinstance(max_tokens, int) or not isinstance(max_messages, int):
        return messages, False, 0, 0, "none", 1.0, False
    compact_guidance = profile in ("continue-local", "embedded-assist") and _looks_like_compact_guidance_request(messages)
    if profile in ("continue-local", "embedded-assist") and _looks_like_strict_reply_only(messages):
        max_tokens = min(max_tokens, 1024)
        max_messages = min(max_messages, 8)
    if compact_guidance:
        max_tokens = min(max_tokens, 512)
        max_messages = min(max_messages, 4)

    before = _estimate_messages_tokens(messages)
    if before <= max_tokens and len(messages) <= max_messages:
        return messages, False, before, before, "none", 1.0, False

    system_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "system"]
    non_system = [m for m in messages if isinstance(m, dict) and m.get("role") != "system"]
    latest_user = ""
    for msg in reversed(non_system):
        if msg.get("role") == "user":
            latest_user = _extract_content_text(msg)
            break

    selected, relevance, reasoning_policy = await _select_non_system(non_system, latest_user)
    if selected:
        non_system = selected

    kept = non_system[-max_messages:]
    if system_msgs:
        kept = [system_msgs[-1]] + kept

    while kept and _estimate_messages_tokens(kept) > max_tokens:
        if len(kept) > 1 and isinstance(kept[0], dict) and kept[0].get("role") == "system":
            if len(kept) > 2:
                del kept[1]
            else:
                break
        else:
            kept.pop(0)

    if kept and _estimate_messages_tokens(kept) > max_tokens:
        largest_idx = max(
            range(len(kept)),
            key=lambda idx: _estimate_tokens(_extract_content_text(kept[idx])) if isinstance(kept[idx], dict) else 0,
        )
        reserved_tokens = 0
        for idx, message in enumerate(kept):
            if idx == largest_idx or not isinstance(message, dict):
                continue
            reserved_tokens += _estimate_tokens(_extract_content_text(message))
        min_truncate_tokens = 48 if compact_guidance else 128
        available_tokens = max(min_truncate_tokens, max_tokens - reserved_tokens)
        if isinstance(kept[largest_idx], dict):
            kept[largest_idx] = _truncate_message_to_token_budget(kept[largest_idx], available_tokens)

    after = _estimate_messages_tokens(kept)
    gate_applied = False
    if (
        ANSWERABILITY_GATE_ENABLED
        and latest_user.strip()
        and profile in ("continue-local", "embedded-assist")
        and relevance < ANSWERABILITY_MIN_SCORE
    ):
        gate_applied = True
        gate_msg = {
            "role": "system",
            "content": (
                "[answerability-gate] Retrieval confidence is low. "
                "Ask a clarifying question before making assumptions, then answer briefly."
            ),
        }
        if not any(isinstance(m, dict) and "[answerability-gate]" in str(m.get("content", "")) for m in kept):
            kept = [gate_msg] + kept
    mode = f"{reasoning_policy}+trim"
    return kept, True, before, after, mode, relevance, gate_applied

def _profile_card(profile: str) -> str:
    if not PROFILE_CARDS_ENABLED:
        return ""
    return str(_profile_settings(profile).get("profileCard") or "").strip()

def _skip_profile_card_for_messages(profile: str, messages: list) -> bool:
    if profile not in ("continue-local", "embedded-assist"):
        return False
    return _looks_like_strict_reply_only(messages)

def _apply_compact_local_response_budget(payload: dict, profile: str) -> dict:
    if not isinstance(payload, dict) or profile not in ("continue-local", "embedded-assist"):
        return payload
    messages = payload.get("messages")
    if not _looks_like_compact_guidance_request(messages):
        return payload
    current = payload.get("max_tokens")
    try:
        current_int = int(current) if current is not None else 0
    except Exception:
        current_int = 0
    target = 128
    if current_int > 0:
        target = min(target, current_int)
    payload["max_tokens"] = max(32, target)
    return payload

def _ensure_profile_card(messages: list, profile: str) -> tuple[list, bool]:
    if not isinstance(messages, list):
        return messages, False
    if _skip_profile_card_for_messages(profile, messages):
        return messages, False
    card = _profile_card(profile)
    if not card:
        return messages, False
    for m in messages:
        if isinstance(m, dict) and m.get("role") == "system" and card in str(m.get("content", "")):
            return messages, False
    return ([{"role": "system", "content": card}] + list(messages)), True

def _compact_guidance_contract() -> str:
    return (
        "[compact-guidance] Return at most 3 numbered lines. "
        "Keep each line short and actionable. "
        "No preamble, no explanation, no code fences."
    )

def _apply_compact_guidance_contract(messages: list, profile: str) -> tuple[list, bool]:
    if (
        profile not in ("continue-local", "embedded-assist")
        or not isinstance(messages, list)
        or not _looks_like_compact_guidance_request(messages)
    ):
        return messages, False
    contract = _compact_guidance_contract()
    for message in messages:
        if (
            isinstance(message, dict)
            and message.get("role") == "system"
            and contract in str(message.get("content", ""))
        ):
            return messages, False
    return ([{"role": "system", "content": contract}] + list(messages)), True

async def _get_hints(query: str):
    if not HYBRID_URL or not query.strip() or _hints_client is None:
        return None
    from urllib.parse import urlencode
    params = urlencode({"q": query[:200], "limit": HINTS_LIMIT})
    hdrs = {}
    if HYBRID_API_KEY:
        hdrs["X-API-Key"] = HYBRID_API_KEY
    
    breaker = LOCAL_CIRCUIT_BREAKERS.get("hybrid")
    
    async def _do_hint_fetch():
        resp = await _hints_client.get(f"{HYBRID_URL}/hints?{params}", headers=hdrs)
        if resp.status_code != 200:
            return None
        return resp

    try:
        resp = await retry_with_backoff(
            breaker.call,
            _do_hint_fetch,
            max_attempts=2,
            breaker=breaker,
            retry_on_exceptions=(httpx.TimeoutException, httpx.NetworkError),
        )
        if resp is None:
            return None
        
        data = resp.json()
        hints_list = data.get("hints", []) if isinstance(data, dict) else []
        if not hints_list:
            return None
        lines = ["[AI stack — tools available for this task]"]
        for item in hints_list:
            if isinstance(item, dict):
                name = item.get("name") or item.get("title") or item.get("id") or ""
                # hints use "snippet" not "description" — fall through to snippet as content
                desc = item.get("description") or item.get("summary") or item.get("snippet") or ""
                if name and desc:
                    lines.append(f"- {name}: {desc}")
                elif name:
                    lines.append(f"- {name}")
        return "\n".join(lines)
    except Exception:
        return None

def _loading_error_payload(detail: dict | None = None) -> dict:
    payload = {
        "error": {
            "message": "local model is still loading",
            "type": "local_model_loading",
            "target": "local",
            "retry_after_s": 20,
        }
    }
    if detail:
        payload["error"]["detail"] = detail
    return payload

def _is_local_loading_response(status_code: int, content: bytes) -> bool:
    if status_code != 503:
        return False
    try:
        body = json.loads(content.decode("utf-8", errors="replace"))
    except Exception:
        return False
    error = body.get("error") if isinstance(body, dict) else None
    message = str((error or {}).get("message") or "").strip().lower()
    return "loading model" in message

async def _probe_local_upstream_state() -> dict | None:
    try:
        if _local_health_client is not None:
            resp = await _local_health_client.get(f"{LLAMA_URL}/health")
        else:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=2.0, read=4.0, write=2.0, pool=2.0)) as client:
                resp = await client.get(f"{LLAMA_URL}/health")
        if _is_local_loading_response(resp.status_code, resp.content):
            return _loading_error_payload({"health_status_code": resp.status_code})
    except httpx.HTTPError as exc:
        return {
            "error": {
                "message": "local upstream is not reachable yet",
                "type": "local_upstream_unreachable",
                "target": "local",
                "detail": str(exc),
                "retry_after_s": 10,
            }
        }
    return None

def _parse_prometheus_gauge(metrics_text: str, metric_name: str) -> float | None:
    prefix = f"{metric_name} "
    for line in metrics_text.splitlines():
        if line.startswith(prefix):
            raw_value = line[len(prefix):].strip()
            try:
                return float(raw_value)
            except ValueError:
                return None
    return None

async def _local_runtime_health_snapshot() -> dict:
    local_slot_capacity = int(LOCAL_CONCURRENCY)
    local_slot_available = int(_local_sem._value) if _local_sem is not None else local_slot_capacity
    local_slot_busy = local_slot_available <= 0
    snapshot = {
        "slot_capacity": local_slot_capacity,
        "slot_available": local_slot_available,
        "slot_busy": local_slot_busy,
        "source": "switchboard_semaphore",
        "llama_metrics_available": False,
    }
    active_request = _local_active_request_snapshot()
    if active_request:
        snapshot["active_request"] = active_request
    last_completion = _local_last_completion_snapshot()
    if last_completion:
        snapshot["last_completion"] = last_completion
    try:
        if _local_health_client is not None:
            resp = await _local_health_client.get(f"{LLAMA_URL}/metrics")
        else:
            async with httpx.AsyncClient(timeout=httpx.Timeout(connect=2.0, read=4.0, write=2.0, pool=2.0)) as client:
                resp = await client.get(f"{LLAMA_URL}/metrics")
        if resp.status_code >= 400:
            snapshot["llama_metrics_status_code"] = resp.status_code
            return snapshot
        metrics_text = resp.text
        snapshot["llama_metrics_available"] = True
        requests_processing = _parse_prometheus_gauge(metrics_text, "llamacpp:requests_processing")
        requests_deferred = _parse_prometheus_gauge(metrics_text, "llamacpp:requests_deferred")
        busy_slots_per_decode = _parse_prometheus_gauge(metrics_text, "llamacpp:n_busy_slots_per_decode")
        if requests_processing is not None:
            snapshot["requests_processing"] = int(requests_processing)
        if requests_deferred is not None:
            snapshot["requests_deferred"] = int(requests_deferred)
        if busy_slots_per_decode is not None:
            snapshot["busy_slots_per_decode"] = busy_slots_per_decode
        snapshot["slot_busy"] = bool(
            snapshot.get("slot_busy")
            or (requests_processing is not None and requests_processing >= 1)
        )
        if snapshot["slot_busy"] and snapshot["source"] == "switchboard_semaphore":
            snapshot["source"] = "switchboard_semaphore+llama_metrics"
    except Exception as exc:
        snapshot["llama_metrics_error"] = f"{type(exc).__name__}: {exc}"
    return snapshot

def _profile_settings(profile: str) -> dict:
    settings = PROFILE_CATALOG.get(profile)
    if not isinstance(settings, dict):
        settings = PROFILE_CATALOG.get("default", {})
    return settings if isinstance(settings, dict) else {}

def _profile_flag(profile: str, key: str, fallback):
    value = _profile_settings(profile).get(key, fallback)
    return fallback if value is None else value

def _route_target(request: Request, payload: dict | None, profile: str) -> str:
    profile_provider = str(_profile_settings(profile).get("forceProvider") or "").strip().lower()
    if profile_provider == "local":
        return "local"
    if profile_provider == "remote":
        return "remote" if REMOTE_URL else "local"

    route_hint = request.headers.get(ROUTE_HINT_HEADER, "").strip().lower()
    provider_hint = request.headers.get(PROVIDER_HINT_HEADER, "").strip().lower()

    if ROUTING_MODE == "local_only":
        return "local"
    if ROUTING_MODE == "remote_only":
        return "remote" if REMOTE_URL else "local"

    if route_hint in ("local", "remote"):
        return route_hint if (route_hint != "remote" or REMOTE_URL) else "local"
    if provider_hint in ("local", "remote"):
        return provider_hint if (provider_hint != "remote" or REMOTE_URL) else "local"

    model = ""
    if isinstance(payload, dict):
        model = str(payload.get("model", "")).strip().lower()
    if any(model.startswith(prefix) for prefix in REMOTE_MODEL_PREFIXES):
        return "remote" if REMOTE_URL else "local"

    # Phase 158: intent-based routing — fires only when no explicit override was set
    intent_target = _classify_routing_intent(payload)
    if intent_target is not None:
        return intent_target

    if DEFAULT_PROVIDER == "remote" and REMOTE_URL:
        return "remote"
    return "local"

def _remote_model_alias(name: str) -> str:
    lowered = (name or "").strip().lower()
    if lowered in ("free", "budget", "cheap"):
        return REMOTE_MODEL_ALIAS_FREE
    if lowered in ("gemini", "google", "planner", "general"):
        return REMOTE_MODEL_ALIAS_GEMINI
    if lowered in ("coding", "code", "coder"):
        return REMOTE_MODEL_ALIAS_CODING
    if lowered in ("reasoning", "architecture", "thinking"):
        return REMOTE_MODEL_ALIAS_REASONING
    if lowered in ("tool", "tools", "tool-calling", "tool_calling", "function", "function-calling"):
        return REMOTE_MODEL_ALIAS_TOOL_CALLING
    return ""

def _rewrite_model(payload: dict, profile: str) -> dict:
    if not isinstance(payload, dict):
        return payload
    model = str(payload.get("model", ""))
    alias_model = ""
    if REMOTE_MODEL_ALIASES_ENABLED:
        alias_model = str(_profile_settings(profile).get("modelAlias") or "").strip()
    for prefix in REMOTE_MODEL_PREFIXES:
        if model.lower().startswith(prefix):
            suffix = model[len(prefix):] or "default"
            alias_model = alias_model or _remote_model_alias(suffix)
            payload["model"] = alias_model or suffix
            break
    if model.lower().startswith("local/"):
        payload["model"] = model[len("local/"):] or "local-model"
    elif alias_model and (not model or not any(model.lower().startswith(p) for p in REMOTE_MODEL_PREFIXES)):
        payload["model"] = alias_model
    return payload

def _apply_local_thinking_profile(payload: dict, profile: str, target_type: str) -> dict:
    # Disable thinking for all local targets by default — thinking tokens are
    # filtered from the OpenAI response content field, producing empty responses
    # unless the profile is an explicit local reasoning profile.
    if not isinstance(payload, dict) or target_type != "local":
        return payload
    kwargs = payload.get("chat_template_kwargs")
    if not isinstance(kwargs, dict):
        kwargs = {}

    # FORCE thinking OFF for all local targets unless explicitly allowed for a reasoning profile.
    # Local Qwen3-35B on llama.cpp requires this to prevent empty response fields.
    # We override caller-supplied True to False here to protect against agentic drift.
    current_val = kwargs.get("enable_thinking")
    is_reasoning_profile = "reasoning" in profile.lower()

    if current_val is True and not is_reasoning_profile:
        kwargs = dict(kwargs)
        kwargs["enable_thinking"] = False
        payload["chat_template_kwargs"] = kwargs
    elif "enable_thinking" not in kwargs:
        kwargs = dict(kwargs)
        kwargs["enable_thinking"] = False
        payload["chat_template_kwargs"] = kwargs
    return payload

async def _call_upstream_with_resilience(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict,
    json_body: Optional[dict] = None,
    content: Optional[bytes] = None,
    params: Optional[dict] = None,
    stream: bool = False,
    service_name: str = "llama",
) -> httpx.Response:
    """Execute upstream request with retries and circuit breaker."""
    # We determine the registry based on service type.
    # Remote services (e.g. OpenRouter) use REMOTE_CIRCUIT_BREAKERS,
    # Local services (e.g. local models, tools) use LOCAL_CIRCUIT_BREAKERS.
    if service_name == "llama":
        breaker = None
    elif service_name in ["remote", "openrouter"]:
        breaker = REMOTE_CIRCUIT_BREAKERS.get(service_name)
    else:
        breaker = LOCAL_CIRCUIT_BREAKERS.get(service_name)
    
    async def _do_request():
        if stream:
            req = client.build_request(
                method=method,
                url=url,
                headers=headers,
                content=content,
                json=json_body,
                params=params,
            )
            return await client.send(req, stream=True)
        else:
            return await client.request(
                method=method,
                url=url,
                headers=headers,
                json=json_body,
                content=content,
                params=params,
            )

    try:
        # Wrap retry logic around the circuit breaker call
        if breaker:
            return await retry_with_backoff(
                breaker.call,
                _do_request,
                max_attempts=3,
                breaker=breaker,
                retry_on_exceptions=(httpx.TimeoutException, httpx.NetworkError),
            )
        else:
            return await retry_with_backoff(
                _do_request,
                max_attempts=3,
                retry_on_exceptions=(httpx.TimeoutException, httpx.NetworkError),
            )
    except CircuitBreakerOpenError:
        raise
    except Exception as exc:
        print(f"[switchboard] upstream_call_failed service={service_name} error={exc}", file=sys.stderr)
        raise

def _effective_profile(request: Request) -> str:
    profile = request.headers.get(PROFILE_HINT_HEADER, "").strip().lower()
    if not profile:
        profile = request.query_params.get("ai_profile", "").strip().lower()
    allowed = tuple(PROFILE_CATALOG.keys()) or ("default",)
    return profile if profile in allowed else "default"

def _budget_state_current() -> dict:
    today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    state = {"date": today, "remote_tokens_used": 0}
    if not REMOTE_BUDGET_STATE_PATH:
        return state
    try:
        with open(REMOTE_BUDGET_STATE_PATH, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, dict) and loaded.get("date") == today:
            state["remote_tokens_used"] = int(loaded.get("remote_tokens_used", 0) or 0)
    except Exception:
        pass
    return state

def _budget_state_save(remote_tokens_used: int) -> None:
    if not REMOTE_BUDGET_STATE_PATH:
        return
    state_path = pathlib.Path(REMOTE_BUDGET_STATE_PATH)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
        "remote_tokens_used": max(0, int(remote_tokens_used)),
    }
    tmp = state_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    tmp.replace(state_path)

def _remote_budget_status(projected_delta: int) -> tuple[bool, dict]:
    state = _budget_state_current()
    used = int(state.get("remote_tokens_used", 0) or 0)
    projected = used + max(0, int(projected_delta))
    remaining = max(0, REMOTE_DAILY_TOKEN_CAP - used) if REMOTE_DAILY_TOKEN_CAP > 0 else None
    allowed = REMOTE_DAILY_TOKEN_CAP <= 0 or projected <= REMOTE_DAILY_TOKEN_CAP
    return allowed, {
        "date": state.get("date"),
        "remote_tokens_used": used,
        "projected_remote_tokens_used": projected,
        "remote_daily_token_cap": REMOTE_DAILY_TOKEN_CAP,
        "remote_tokens_remaining": remaining,
    }

def _timeout_for(target_type: str, is_stream: bool) -> httpx.Timeout:
    if is_stream:
        read_timeout = STREAM_READ_TIMEOUT_S
    elif target_type == "remote":
        read_timeout = REMOTE_READ_TIMEOUT_S
    else:
        read_timeout = LOCAL_READ_TIMEOUT_S
    return httpx.Timeout(
        connect=CONNECT_TIMEOUT_S,
        read=read_timeout,
        write=WRITE_TIMEOUT_S,
        pool=POOL_TIMEOUT_S,
    )

def _is_self_referential(url: str) -> bool:
    if not url:
        return False
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        port = parsed.port
        if port is None:
            port = 443 if parsed.scheme == "https" else 80
        return host in {"127.0.0.1", "localhost", "::1"} and port == PORT
    except Exception:
        return False

def _response_headers(raw_headers: dict) -> dict:
    hop = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
        "content-length",
    }
    return {k: v for k, v in raw_headers.items() if k.lower() not in hop}

def _startup_prefix_warm_messages(profile: str) -> list[dict]:
    card = _profile_card(profile)
    user_content = f"Warm the {profile} local editor lane."
    if profile in ("continue-local", "embedded-assist"):
        user_content = "Diagnose why the local editor path is slow and return 3 compact next steps."
    messages = [{"role": "user", "content": user_content}]
    messages, _ = _apply_compact_guidance_contract(messages, profile)
    if card:
        messages.insert(0, {"role": "system", "content": card})
    return messages

async def _warm_local_profile_prefix(profile: str) -> None:
    if not STARTUP_PREFIX_WARM_ENABLED:
        return
    payload = build_llama_payload(
        _startup_prefix_warm_messages(profile),
        max_tokens=4,
        temperature=0,
        model="AUTODETECT",
        cache_prompt=True,
    )
    try:
        await asyncio.sleep(1.0)
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=2.0, read=20.0, write=5.0, pool=2.0)) as client:
            response = await client.post(f"{LLAMA_URL}/v1/chat/completions", json=payload)
        response.raise_for_status()
    except Exception as exc:
        print(f"[switchboard] startup_prefix_warm_failed profile={profile} error={exc}")

# --- Lifecycle ---

@app.on_event("startup")
async def _startup():
    global _local_sem, _remote_sem, _hints_client, _embed_client, _local_health_client, _local_active_request, _local_last_completion
    _local_sem = asyncio.Semaphore(LOCAL_CONCURRENCY)
    _remote_sem = asyncio.Semaphore(REMOTE_CONCURRENCY)
    _local_active_request = None
    _local_last_completion = None
    _hints_client = httpx.AsyncClient(timeout=HINTS_TIMEOUT_S)
    _embed_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=2.0, read=SEMANTIC_EMBED_TIMEOUT_S, write=2.0, pool=2.0)
    )
    _local_health_client = httpx.AsyncClient(
        timeout=httpx.Timeout(connect=2.0, read=4.0, write=2.0, pool=2.0)
    )
    asyncio.create_task(_warm_local_profile_prefix("continue-local"))
    await asyncio.to_thread(_routing_log_init)

@app.on_event("shutdown")
async def _shutdown():
    global _hints_client, _embed_client, _local_health_client, _local_active_request, _local_last_completion
    for client in (_hints_client, _embed_client, _local_health_client):
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass
    _local_active_request = None
    _local_last_completion = None
    _hints_client = _embed_client = _local_health_client = None

# --- Health ---

def _routing_log_init() -> None:
    """Resolve log path, create parent dir, and warm the ring from existing records."""
    global _ROUTING_LOG_PATH
    repo_root = os.getenv("REPO_PATH", "").strip()
    if not repo_root:
        return
    log_path = pathlib.Path(repo_root) / ".agents" / "telemetry" / "routing-decisions.jsonl"
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        _ROUTING_LOG_PATH = log_path
        # Warm ring from persisted records (skip lines older than ring window).
        if log_path.exists():
            cutoff = time.time() - 7 * 86400  # only load last 7 days into ring
            with open(log_path, encoding="utf-8", errors="replace") as fh:
                for raw in fh:
                    raw = raw.strip()
                    if not raw:
                        continue
                    try:
                        rec = json.loads(raw)
                        if rec.get("ts", 0) >= cutoff:
                            _routing_ring.append(rec)
                    except Exception:
                        pass
    except Exception as exc:
        print(f"[switchboard] routing_log_init failed: {exc}", file=sys.stderr)


def _routing_log_append(ts: float, local: bool, profile: str) -> None:
    """Append one routing decision to the JSONL log. Threadsafe; no-op if path unset."""
    if _ROUTING_LOG_PATH is None:
        return
    record = json.dumps({"ts": ts, "local": local, "profile": profile, "event_type": "routing_decision"})
    try:
        with _routing_log_lock:
            with open(_ROUTING_LOG_PATH, "a", encoding="utf-8") as fh:
                fh.write(record + "\n")
    except Exception as exc:
        print(f"[switchboard] routing_log_append failed: {exc}", file=sys.stderr)


def _routing_stats_snapshot() -> dict:
    """Compute local/remote percentages from the in-memory routing ring."""
    now = time.time()
    windows = {"1h": 3600, "24h": 86400, "7d": 604800, "all": None}
    result: dict = {}
    for label, seconds in windows.items():
        subset = [r for r in _routing_ring if seconds is None or (now - r["ts"]) <= seconds]
        total = len(subset)
        local_n = sum(1 for r in subset if r.get("local") is True)
        remote_n = total - local_n
        result[label] = {
            "count": total,
            "local_count": local_n,
            "remote_count": remote_n,
            "local_pct": round(100 * local_n / total, 1) if total else None,
            "remote_pct": round(100 * remote_n / total, 1) if total else None,
        }
    return result


@app.get("/health")
async def health():
    local_runtime = await _local_runtime_health_snapshot()
    local_lane_status = _local_lane_status(local_runtime)
    return {
        "status": "ok",
        "routing_mode": ROUTING_MODE,
        "default_provider": DEFAULT_PROVIDER,
        "remote_configured": bool(REMOTE_URL),
        "profiles": PROFILE_CATALOG,
        "tool_working_set": {
            "enabled": bool(TOOL_WORKING_SET_ENABLED),
            "remote_enabled": bool(REMOTE_TOOL_WORKING_SET_ENABLED),
            "active_schema_limit": int(ACTIVE_TOOL_SCHEMA_LIMIT),
            "virtual_tools": [VIRTUAL_TOOL_LEASE_NAME],
            "intents": sorted(_TOOL_BUNDLES.keys()),
            "bundles": {name: sorted(tools) for name, tools in _TOOL_BUNDLES.items()},
        },
        "context_output_gc": {
            "enabled": bool(CONTEXT_OUTPUT_GC_ENABLED),
            "min_chars": int(CONTEXT_OUTPUT_GC_MIN_CHARS),
            "summary_chars": int(CONTEXT_OUTPUT_GC_SUMMARY_CHARS),
            "artifact_dir": CONTEXT_ARTIFACT_DIR,
            "dedupe_enabled": bool(TOOL_RESULT_DEDUPE_ENABLED),
        },
        "local_runtime": local_runtime,
        "local_lane_status": local_lane_status,
        "circuit_breakers": {
            "local": LOCAL_CIRCUIT_BREAKERS.get_all_states(),
            "remote": REMOTE_CIRCUIT_BREAKERS.get_all_states()
        },
        "routing_stats": _routing_stats_snapshot(),
    }

# --- Main Proxy Route ---

@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(path: str, request: Request):
    body = await request.body()
    payload = None
    input_trimmed = False
    input_tokens_before = 0
    input_tokens_after = 0
    input_policy = "none"
    profile_card_applied = False
    relevance = 1.0
    gate_applied = False
    tool_working_set = None
    context_output_gc = None
    if body:
        try:
            payload = await request.json()
        except Exception:
            payload = None

    profile = _effective_profile(request)
    target_type = _route_target(request, payload, profile)
    target = REMOTE_URL if target_type == "remote" and REMOTE_URL else LLAMA_URL
    # Record routing decision for dashboard stats (chat/completions only — skip health polls).
    if path == "chat/completions":
        _ts = time.time()
        _rec = {"ts": _ts, "local": target_type == "local", "profile": profile}
        _routing_ring.append(_rec)
        # Persist asynchronously — survives restarts, trimmed by data-retention (14d TTL).
        asyncio.create_task(asyncio.to_thread(_routing_log_append, _ts, target_type == "local", profile))
    if profile in ("remote-default", "remote-gemini", "remote-free", "remote-coding", "remote-reasoning", "remote-tool-calling") and not REMOTE_URL:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "message": f"{profile} profile requested but no REMOTE_LLM_URL is configured",
                    "type": "route_configuration_error",
                }
            },
        )
    if profile == "embedding-local":
        if path not in ("embeddings", "models"):
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": "embedding-local profile only supports /v1/embeddings and /v1/models",
                        "type": "invalid_profile_for_endpoint",
                    }
                },
            )
        if not EMBEDDING_URL:
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "message": "embedding-local profile requested but EMBEDDING_URL is not configured",
                        "type": "route_configuration_error",
                    }
                },
            )
        target = EMBEDDING_URL
    if path == "embeddings" and target_type == "local" and EMBEDDING_URL:
        target = EMBEDDING_URL
    if _is_self_referential(target):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "message": "switchboard upstream points to itself; refusing recursive route",
                    "type": "route_configuration_error",
                }
            },
        )

    model_alias_used = ""
    if isinstance(payload, dict):
        original_model = str(payload.get("model", ""))
        payload = _rewrite_model(payload, profile)
        rewritten_model = str(payload.get("model", ""))
        if rewritten_model and rewritten_model != original_model:
            model_alias_used = rewritten_model
        payload, remote_working_set = _filter_remote_tools_for_working_set(payload, profile)
        if remote_working_set:
            tool_working_set = remote_working_set
        payload = _apply_local_thinking_profile(payload, profile, target_type)
        payload = _apply_compact_local_response_budget(payload, profile)
        if path == "chat/completions":
            msgs = payload.get("messages")
            if isinstance(msgs, list):
                with_card, card_applied = _ensure_profile_card(msgs, profile)
                with_guidance_contract, _ = _apply_compact_guidance_contract(with_card, profile)
                
                # --- Loop guard integration ---
                loop_msg = await _detect_loop(with_guidance_contract)
                if loop_msg:
                    already_injected = any(
                        isinstance(m, dict) and "[loop-guard]" in str(m.get("content", ""))
                        for m in with_guidance_contract
                    )
                    if already_injected:
                        return JSONResponse(status_code=503, content={"error": "loop_detected"})
                    else:
                        with_guidance_contract = [{"role": "system", "content": loop_msg}] + list(with_guidance_contract)
                        _log_loop_event(profile, LOOP_DETECT_THRESHOLD, LOOP_DETECT_WINDOW)
                
                trimmed, did_trim, before, after, policy, rel, gate = await _trim_profile_messages(with_guidance_contract, profile)
                payload["messages"] = trimmed
                input_trimmed = did_trim
                input_tokens_before = before
                input_tokens_after = after
                input_policy = policy
                profile_card_applied = card_applied
                relevance = rel
                gate_applied = gate
            else:
                relevance = 1.0
                gate_applied = False
        body = json.dumps(payload).encode("utf-8")

    remote_token_delta = _estimate_payload_tokens(payload)
    remote_budget = None
    payload_model = str(payload.get("model", "")).strip().lower() if isinstance(payload, dict) else ""
    explicit_remote = (
        str(_profile_settings(profile).get("forceProvider") or "").strip().lower() == "remote"
        or request.headers.get(ROUTE_HINT_HEADER, "").strip().lower() == "remote"
        or request.headers.get(PROVIDER_HINT_HEADER, "").strip().lower() == "remote"
        or any(payload_model.startswith(prefix) for prefix in REMOTE_MODEL_PREFIXES)
    )
    budget_fallback = False
    if target_type == "remote" and REMOTE_DAILY_TOKEN_CAP > 0:
        allowed, remote_budget = _remote_budget_status(remote_token_delta)
        if not allowed:
            if REMOTE_BUDGET_FALLBACK_LOCAL and not explicit_remote and path != "embeddings":
                target_type = "local"
                target = EMBEDDING_URL if path == "embeddings" and EMBEDDING_URL else LLAMA_URL
                budget_fallback = True
            else:
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "message": "remote daily token budget exhausted",
                            "type": "remote_budget_exhausted",
                            "budget": remote_budget,
                        }
                    },
                )

    hints_skipped = False
    use_hints = bool(_profile_flag(profile, "injectHints", HINTS_INJECT))
    if use_hints and path == "chat/completions" and isinstance(payload, dict):
        messages = payload.get("messages") or []
        first_user = next((m.get("content", "") for m in messages if m.get("role") == "user"), "")
        if first_user:
            hint_text = await _get_hints(str(first_user))
            if hint_text:
                sys_idxs = [i for i, m in enumerate(messages) if m.get("role") == "system"]
                if sys_idxs:
                    i = sys_idxs[0]
                    messages[i] = dict(messages[i])
                    messages[i]["content"] = hint_text + "\n\n" + messages[i]["content"].lstrip()
                else:
                    messages = [{"role": "system", "content": hint_text}] + list(messages)
                payload["messages"] = messages
                body = json.dumps(payload).encode("utf-8")
            else:
                hints_skipped = True
        else:
            hints_skipped = True
    elif use_hints:
        hints_skipped = True

    if target_type == "local" and path == "chat/completions" and isinstance(payload, dict) and not payload.get("cache_prompt"):
        payload["cache_prompt"] = True
        body = json.dumps(payload).encode("utf-8")

    if (
        target_type == "local"
        and path == "chat/completions"
        and profile not in ("coordinator-internal", "embedding-local", "local-tool-calling")
        and isinstance(payload, dict)
        and not payload.get("stream")
    ):
        payload["stream"] = True
        body = json.dumps(payload).encode("utf-8")
        print(f"[switchboard] forced stream=True for local chat/completions profile={profile}", file=sys.stderr)

    is_stream = bool(isinstance(payload, dict) and payload.get("stream") is True)
    local_tool_execution_used = False
    local_tool_calls_used = 0

    hop_by_hop = {
        "host", "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
        "te", "trailer", "transfer-encoding", "upgrade", "content-length", "accept-encoding",
    }
    headers = {k: v for k, v in request.headers.items() if k.lower() not in hop_by_hop}
    for h in (ROUTE_HINT_HEADER, PROVIDER_HINT_HEADER, PROFILE_HINT_HEADER):
        headers.pop(h, None)
    headers["Accept-Encoding"] = "identity"
    headers["Connection"] = "close"
    if target_type == "remote" and REMOTE_API_KEY:
        headers["Authorization"] = f"Bearer {REMOTE_API_KEY}"
        headers.setdefault("HTTP-Referer", "https://github.com/MasterofNull/NixOS-Dev-Quick-Deploy")
        headers.setdefault("X-Title", "NixOS-Dev-Quick-Deploy AI Harness")

    timeout = _timeout_for(target_type, is_stream)
    sem = _remote_sem if target_type == "remote" else _local_sem

    # Check for lane reservation
    is_priority = request.headers.get("X-AI-Lane") == "high-priority"
    reserved_slots = int(os.environ.get("SWB_RESERVED_SLOTS", "0"))
    total_concurrency = int(os.environ.get("SWB_LOCAL_CONCURRENCY", "1"))
    
    # Logic: If not priority, we can only proceed if total_slots - active_slots > reserved_slots
    if target_type == "local" and _local_sem is not None:
        active_slots = total_concurrency - _local_sem._value
        if not is_priority and (total_concurrency - active_slots <= reserved_slots):
            # Queueing logic: instead of fail-fast, allow wait but don't force-preempt
            pass

    req_id = request.headers.get("X-Request-ID") or str(time.time_ns())
    print(f"[switchboard] route target={target_type} path={path} profile={profile} stream={is_stream} req_id={req_id}", file=sys.stderr)

    try:
        async with sem:
            local_active_request_id = ""
            retain_local_request_until_stream_close = False
            if target_type == "local" and path == "chat/completions":
                local_active_request_id = _begin_local_active_request(path, profile, payload, is_stream)
            try:
                if (
                    path == "chat/completions"
                    and profile == "local-tool-calling"
                    and target_type == "local"
                    and isinstance(payload, dict)
                    and not is_stream
                ):
                    try:
                        run_id = request.headers.get("x-agent-run-id") or payload.get("session_id") or "unknown-run"
                        local_body, local_tool_calls_used = await _execute_local_tool_calling(payload, run_id=run_id)
                        if isinstance(local_body, dict) and isinstance(local_body.get("tool_working_set"), dict):
                            tool_working_set = local_body.get("tool_working_set")
                        if isinstance(local_body, dict) and isinstance(local_body.get("context_output_gc"), dict):
                            context_output_gc = local_body.get("context_output_gc")
                    except ValueError as exc:
                        return JSONResponse(
                            status_code=400,
                            content={"error": {"message": str(exc), "type": "invalid_local_tool_request"}},
                        )
                    except RuntimeError as exc:
                        return JSONResponse(
                            status_code=502,
                            content={"error": {"message": str(exc), "type": "local_tool_execution_error"}},
                        )
                    response = JSONResponse(status_code=200, content=local_body)
                    local_tool_execution_used = True
                else:
                    client = httpx.AsyncClient(timeout=timeout)
                    service_name = "llama" if target_type == "local" else "remote"
                    try:
                        if is_stream:
                            upstream = await _call_upstream_with_resilience(
                                client=client,
                                method=request.method,
                                url=f"{target}/v1/{path}",
                                headers=headers,
                                content=body,
                                params=dict(request.query_params),
                                stream=True,
                                service_name=service_name,
                            )

                            full_content = ""
                            token_usage_emitted = False
                            async def _iter():
                                nonlocal full_content, token_usage_emitted
                                try:
                                    async for chunk in upstream.aiter_bytes():
                                        # Phase 1: Track content for token estimation fallback
                                        try:
                                            chunk_str = chunk.decode("utf-8", errors="ignore")
                                            for line in chunk_str.splitlines():
                                                if line.startswith("data: "):
                                                    data_str = line[6:]
                                                    if data_str == "[DONE]": break
                                                    data = json.loads(data_str)
                                                    delta = data.get("choices", [{}])[0].get("delta", {})
                                                    if "content" in delta:
                                                        full_content += delta["content"]
                                                    
                                                    # Check if llama.cpp provided usage in this chunk
                                                    usage = data.get("usage")
                                                    if usage and not token_usage_emitted and run_id != "unknown-run":
                                                        ev = _are.make_event(
                                                            "token_usage",
                                                            source="switchboard",
                                                            run_id=run_id,
                                                            payload={
                                                                "model": payload.get("model", "qwen3.6"),
                                                                "route_profile": profile,
                                                                "tokens": usage
                                                            }
                                                        )
                                                        await asyncio.to_thread(_are.append_jsonl, _AGENT_RUN_EVENTS_PATH, ev)
                                                        token_usage_emitted = True
                                        except Exception:
                                            pass
                                        yield chunk
                                    
                                    # Fallback: Emit estimated usage if stream finished without a usage block
                                    if not token_usage_emitted and run_id != "unknown-run" and full_content:
                                        est_output_tokens = len(full_content) // 4
                                        est_input_tokens = _estimate_payload_tokens(payload)
                                        ev = _are.make_event(
                                            "token_usage",
                                            source="switchboard",
                                            run_id=run_id,
                                            payload={
                                                "model": payload.get("model", "qwen3.6"),
                                                "route_profile": profile,
                                                "tokens": {
                                                    "prompt_tokens": est_input_tokens,
                                                    "completion_tokens": est_output_tokens,
                                                    "total_tokens": est_input_tokens + est_output_tokens,
                                                    "is_estimated": True
                                                }
                                            }
                                        )
                                        await asyncio.to_thread(_are.append_jsonl, _AGENT_RUN_EVENTS_PATH, ev)
                                        token_usage_emitted = True
                                finally:
                                    await upstream.aclose()
                                    await client.aclose()
                                    if local_active_request_id:
                                        _clear_local_active_request(local_active_request_id)

                            retain_local_request_until_stream_close = target_type == "local" and bool(local_active_request_id)
                            response = StreamingResponse(
                                _iter(),
                                status_code=upstream.status_code,
                                headers=_response_headers(dict(upstream.headers)),
                            )
                        else:
                            async with client:
                                upstream = await _call_upstream_with_resilience(
                                    client=client,
                                    method=request.method,
                                    url=f"{target}/v1/{path}",
                                    headers=headers,
                                    content=body,
                                    params=dict(request.query_params),
                                    service_name=service_name,
                                )
                    except CircuitBreakerOpenError:
                        await client.aclose()
                        if local_active_request_id:
                            _clear_local_active_request(local_active_request_id)
                        
                        # Retrieve breaker from correct registry
                        if service_name in ["remote", "openrouter"]:
                            _breaker = REMOTE_CIRCUIT_BREAKERS.get(service_name)
                        else:
                            _breaker = LOCAL_CIRCUIT_BREAKERS.get(service_name)

                        return JSONResponse(
                            status_code=503,
                            content={
                                "error": {
                                    "message": f"Circuit breaker is OPEN for service '{service_name}'",
                                    "type": "service_unavailable",
                                    "retry_after": _breaker.config.reset_timeout,
                                }
                            },
                            headers={"Retry-After": str(int(_breaker.config.reset_timeout))},
                        )
                    except Exception as exc:
                        await client.aclose()
                        if local_active_request_id:
                            _clear_local_active_request(local_active_request_id)
                        print(f"[switchboard] upstream {type(exc).__name__} error target={target_type} path={path} req_id={req_id}: {exc}", file=sys.stderr)
                        return JSONResponse(
                            status_code=502,
                            content={"error": {
                                "message": f"Upstream error: {exc}",
                                "type": "bad_gateway",
                                "target": target_type,
                                "path": path,
                                "req_id": req_id,
                            }},
                        )

                    if not is_stream:
                        if target_type == "local" and _is_local_loading_response(upstream.status_code, upstream.content):
                            return JSONResponse(
                                status_code=503,
                                headers={"Retry-After": "20", "X-AI-Upstream-State": "loading"},
                                content=_loading_error_payload(),
                            )
                        if target_type == "local" and path == "chat/completions":
                            _record_local_completion(path, profile, upstream.status_code, upstream.content)
                        response = Response(
                            content=upstream.content,
                            status_code=upstream.status_code,
                            headers=_response_headers(dict(upstream.headers)),
                        )
            finally:
                if local_active_request_id and not retain_local_request_until_stream_close:
                    _clear_local_active_request(local_active_request_id)
    except httpx.TimeoutException:
        return JSONResponse(
            status_code=504,
            content={"error": {"message": "upstream timeout", "type": "upstream_timeout", "target": target_type}},
        )
    except httpx.HTTPError as exc:
        if target_type == "local":
            loading_state = await _probe_local_upstream_state()
            if loading_state is not None:
                status_code = 503 if loading_state.get("error", {}).get("type") == "local_model_loading" else 502
                headers = {"Retry-After": "20" if status_code == 503 else "10"}
                if status_code == 503:
                    headers["X-AI-Upstream-State"] = "loading"
                return JSONResponse(status_code=status_code, headers=headers, content=loading_state)
        return JSONResponse(
            status_code=502,
            content={"error": {"message": f"upstream transport error: {exc}", "type": "upstream_transport_error", "target": target_type}},
        )

    response.headers["X-AI-Route"] = target_type
    response.headers["X-AI-Profile"] = profile
    if hints_skipped: response.headers["X-AI-Hints-Skipped"] = "timeout"
    if budget_fallback: response.headers["X-AI-Fallback"] = "budget-exceeded"
    if model_alias_used: response.headers["X-AI-Model-Alias"] = model_alias_used
    if local_tool_execution_used:
        response.headers["X-AI-Tool-Execution"] = "local-agent"
        response.headers["X-AI-Tool-Calls-Used"] = str(local_tool_calls_used)
    if isinstance(tool_working_set, dict):
        response.headers["X-AI-Tool-Intent"] = str(tool_working_set.get("intent") or "")
        response.headers["X-AI-Tools-Selected"] = str(tool_working_set.get("selected_count", 0))
        response.headers["X-AI-Tools-Evicted"] = str(tool_working_set.get("evicted_count", 0))
    if isinstance(context_output_gc, dict):
        response.headers["X-AI-Context-GC-Artifacts"] = str(context_output_gc.get("artifacts_written", 0))
        response.headers["X-AI-Context-GC-Pruned-Chars"] = str(context_output_gc.get("raw_chars_pruned", 0))
        response.headers["X-AI-Tool-Duplicate-Calls"] = str(context_output_gc.get("duplicate_tool_calls", 0))
    if remote_budget:
        response.headers["X-AI-Remote-Tokens-Used"] = str(remote_budget.get("remote_tokens_used", 0))
        if remote_budget.get("remote_tokens_remaining") is not None:
            response.headers["X-AI-Remote-Tokens-Remaining"] = str(remote_budget.get("remote_tokens_remaining"))
    if input_trimmed:
        response.headers["X-AI-Input-Trimmed"] = "1"
        response.headers["X-AI-Input-Tokens-Before"] = str(input_tokens_before)
        response.headers["X-AI-Input-Tokens-After"] = str(input_tokens_after)
    if input_policy != "none": response.headers["X-AI-Input-Policy"] = input_policy
    response.headers["X-AI-Retrieval-Confidence"] = f"{relevance:.3f}"
    if gate_applied: response.headers["X-AI-Answerability-Gate"] = "1"
    if profile_card_applied: response.headers["X-AI-Profile-Card"] = "1"
    if target_type == "remote" and REMOTE_DAILY_TOKEN_CAP > 0:
        latest_budget = _budget_state_current()
        used = int(latest_budget.get("remote_tokens_used", 0) or 0) + max(0, int(remote_token_delta))
        _budget_state_save(used)
        response.headers["X-AI-Remote-Tokens-Used"] = str(used)
        response.headers["X-AI-Remote-Tokens-Remaining"] = str(max(0, REMOTE_DAILY_TOKEN_CAP - used))
    return response

if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT, timeout_graceful_shutdown=5)
