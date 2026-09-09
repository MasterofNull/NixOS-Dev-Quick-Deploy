#!/usr/bin/env python3
"""Offline call that asks the local model to propose an AQ-OS installer
selection (P2-b).

The model's reply is constrained to the closed aqos-ai-proposal-v1 schema via
llama.cpp's OpenAI-compatible `response_format: {"type": "json_schema", ...}`
(json_schema-constrained decoding -- the model cannot emit tokens outside the
grammar, so raw Nix/shell/prose is structurally unrepresentable). That
constraint is NEVER trusted alone (OWASP LLM01): every reply is re-validated
through aqos_ai_proposal.validate_proposal(), the authoritative gate from
P2-a, before being returned to the caller.

OFFLINE + fail-closed: only the local llama.cpp server is contacted (env var
LLAMA_URL, matching the convention in scripts/ai/lib/model-client.py -- never
hardcoded elsewhere). The AI proposal is optional and off the critical path:
any HTTP failure, timeout, or malformed reply returns
{"ok": False, "reason": "proposal_unavailable"} rather than raising.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Mapping

_LIB_DIR = Path(__file__).resolve().parent
if str(_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(_LIB_DIR))
import aqos_ai_proposal as proposal  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SHARED = _REPO_ROOT / "ai-stack" / "mcp-servers" / "shared"
if str(_SHARED) not in sys.path:
    sys.path.insert(0, str(_SHARED))
from llm_config import (  # noqa: E402
    LOCAL_QUEUE_OVERHEAD_SECONDS,
    LOCAL_TOK_PER_SEC,
    build_llama_payload,
)

SCHEMA_PATH = _REPO_ROOT / "config" / "schemas" / "aqos-ai-proposal-v1.schema.json"

# Small closed-form JSON reply -- bound generation tightly rather than
# inheriting a general-purpose default budget.
_PROPOSAL_MAX_TOKENS = 512
# Bounded timeout derived from the measured throughput anchor (llm_config's
# LOCAL_TOK_PER_SEC) plus the observed queue-overhead constant, so this stays
# in sync with the hardware anchor instead of a disconnected magic number.
DEFAULT_TIMEOUT = (_PROPOSAL_MAX_TOKENS / LOCAL_TOK_PER_SEC) + LOCAL_QUEUE_OVERHEAD_SECONDS

_SCHEMA_CACHE: dict[str, Any] | None = None


def _load_schema() -> dict[str, Any]:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        _SCHEMA_CACHE = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE


def _catalog_ids(module_catalog: Mapping[str, Any], category: str) -> list[str]:
    return sorted(
        {
            entry.get("id")
            for entry in module_catalog.get("modules", [])
            if entry.get("category") == category
        }
    )


def _build_messages(
    hardware_summary: Mapping[str, Any], module_catalog: Mapping[str, Any]
) -> list[dict[str, str]]:
    """Build the chat request asking the model to pick a catalog selection.

    hardware_summary is expected to already be the closed, redacted summary
    produced by aqos_install_resolver.summarize_hardware() -- this function
    does not perform any further redaction of its own.
    """
    system = (
        "You are proposing an AQ-OS NixOS installer selection for the given "
        "hardware summary. Choose exactly one golden_profile and zero or "
        "more roles, ONLY from the catalog IDs listed in the user message, "
        "and set include_local_ai. Respond with ONLY the JSON object "
        "matching the required schema -- no prose, no explanation, no "
        "markdown fences."
    )
    user = json.dumps(
        {
            "hardware_summary": hardware_summary,
            "available_golden_profiles": _catalog_ids(module_catalog, "profile"),
            "available_roles": _catalog_ids(module_catalog, "role"),
        },
        sort_keys=True,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _post_chat(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
    """POST a chat-completions payload to the local llama.cpp server.

    Isolated in its own function so tests can monkeypatch it -- no real
    network call is ever made from the test suite.
    """
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def propose_selection(
    hardware_summary: Mapping[str, Any],
    module_catalog: Mapping[str, Any],
    *,
    endpoint: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict[str, Any]:
    """Ask the local model to propose an installer selection.

    Returns whatever aqos_ai_proposal.validate_proposal() returns on a
    successful reply -- {"ok": True, "selection": {...}} or
    {"ok": False, "reason": "..."}. Returns
    {"ok": False, "reason": "proposal_unavailable"} if the HTTP call fails,
    times out, or the reply is not shaped like a chat-completion (the AI
    path is optional and off the critical path; callers must have a non-AI
    fallback).
    """
    base_url = (endpoint or os.environ.get("LLAMA_URL", "http://127.0.0.1:8080")).rstrip("/")
    url = f"{base_url}/v1/chat/completions"

    schema = _load_schema()
    messages = _build_messages(hardware_summary, module_catalog)
    # task_type="structured" gives temperature=0.0, frequency_penalty=0.0,
    # enable_thinking=False (chat_template_kwargs, nested -- top-level is
    # silently ignored by this model) via the shared SSOT payload builder.
    payload = build_llama_payload(
        messages,
        task_type="structured",
        max_tokens=_PROPOSAL_MAX_TOKENS,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "aqos_ai_proposal",
                "schema": schema,
                "strict": True,
            },
        },
    )

    try:
        response = _post_chat(url, payload, timeout)
    except Exception:
        return {"ok": False, "reason": "proposal_unavailable"}

    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return {"ok": False, "reason": "proposal_unavailable"}

    if isinstance(content, str):
        raw = content.encode("utf-8")
    elif isinstance(content, (bytes, bytearray)):
        raw = bytes(content)
    else:
        return {"ok": False, "reason": "proposal_unavailable"}

    # AUTHORITATIVE gate -- never trust the schema constraint alone (OWASP
    # LLM01: the model, or a compromised/bypassed server, could still emit
    # anything). validate_proposal() never raises.
    return proposal.validate_proposal(raw, module_catalog)
