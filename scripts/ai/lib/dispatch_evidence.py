#!/usr/bin/env python3
"""Normalized dispatch evidence + local context preflight (routing slice S1).

Two concerns, one module because both feed the same registry row:

* normalize_row(): additive evidence fields for every delegate-to-* registry
  row. Existing keys are never overwritten; unknown values are the literal
  "unknown"/"n/a", never inferred.
* preflight(): measure the assembled local prompt + output allowance against
  the live model context limit BEFORE inference starts.

Context limit SSOT: the running llama-server (/props default_generation_settings.n_ctx, already per-slot),
falling back to config/local-model-config.yaml inference.ctx_size (mirror of
the Nix llamaCpp.ctxSize). Nothing is hardcoded here.
"""
from __future__ import annotations

import json
import math
import os
import re
import urllib.request
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
LOCAL_MODEL_CONFIG = Path(os.environ.get("AQ_LOCAL_MODEL_CONFIG")
                          or REPO_ROOT / "config" / "local-model-config.yaml")

PREFLIGHT_EXIT_CODE = 3
PREFLIGHT_ERROR_EXIT_CODE = 4
# Template framing + tool preamble the server may add that raw bytes do not cover.
FALLBACK_TEMPLATE_MARGIN_TOKENS = 2048
_PROMPT_KEYS = ("messages", "tools", "_tool_schemas", "tool_choice", "grammar", "json_schema",
                "response_format")

_LANE_BY_AGENT_PREFIX = ("local", "codex", "gemini", "claude", "antigravity")


def _lane_of(agent: Any) -> str:
    text = str(agent or "").lower()
    for lane in _LANE_BY_AGENT_PREFIX:
        if text.startswith(lane):
            return lane
    return "unknown"


def normalize_row(row: dict) -> dict:
    """Return row with the normalized evidence fields added (never overwritten)."""
    lane = _lane_of(row.get("agent"))
    defaults = {
        "dispatch_id": row.get("id") or "unknown",
        "source": os.environ.get("DISPATCH_SOURCE") or "unknown",
        "risk": "unknown",
        "complexity": "unknown",
        "model_requested": row.get("requested_model_tier") or "unknown",
        "model_effective": row.get("resolved_model") or "unknown",
        "effort": "n/a",
        "requested_lane": os.environ.get("AQ_REQUESTED_LANE") or "unknown",
        "effective_lane": lane,
        "substitution_reason": "unknown",
        "classification_version": None,
        "policy_version": None,
        "preflight": {"method": "n/a", "measured": None, "limit": None, "verdict": "n/a"},
        "outcome": "unknown",
    }
    saved = _read_preflight_evidence(row)
    if saved is not None:
        defaults["preflight"] = saved
    out = dict(row)
    for key, value in defaults.items():
        out.setdefault(key, value)
    return out


def evidence_path(output_file: Any) -> Optional[Path]:
    """Sidecar where local_preflight leaves an accepted job's verdict."""
    return Path(str(output_file) + ".preflight.json") if output_file else None


def assembled_path(output_file: Any) -> Path:
    """Sidecar holding the exact assembled prompt preflight measured."""
    return Path(str(output_file) + ".assembled.json")


def load_assembled_prompt(path: Any, task_id: str) -> Optional[str]:
    """The measured prompt, or None when missing/unreadable/for another task."""
    try:
        saved = json.loads(Path(path).read_text())
    except (OSError, ValueError, TypeError):
        return None
    if isinstance(saved, dict) and saved.get("task_id") == task_id and isinstance(saved.get("prompt"), str):
        return saved["prompt"]
    return None


def _read_preflight_evidence(row: dict) -> Optional[dict]:
    """The accepted-job preflight written for THIS row (task id must match)."""
    path = evidence_path(row.get("output_file"))
    if path is None or not path.is_file():
        return None
    try:
        saved = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if isinstance(saved, dict) and saved.get("task_id") == row.get("id") \
            and isinstance(saved.get("preflight"), dict):
        return saved["preflight"]
    return None


# ── context limit ───────────────────────────────────────────────────────────

def _http_json(url: str, payload: Optional[dict] = None, timeout: float = 3.0) -> Optional[dict]:
    try:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"},
            method="POST" if data is not None else "GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def context_limit(llama_url: str, config_path: Path = LOCAL_MODEL_CONFIG) -> tuple[Optional[int], str]:
    """Per-slot context tokens and the source it came from."""
    props = _http_json(f"{llama_url}/props")
    if isinstance(props, dict):
        n_ctx = (props.get("default_generation_settings") or {}).get("n_ctx")
        if isinstance(n_ctx, int) and n_ctx > 0:
            return n_ctx, "llama_props"  # llama.cpp reports the per-slot n_ctx here
    try:
        in_inference = False
        for line in config_path.read_text().splitlines():
            if re.match(r"^inference:\s*$", line):
                in_inference = True
                continue
            if in_inference and re.match(r"^\S", line):
                break
            match = re.match(r"^\s+ctx_size:\s*(\d+)", line) if in_inference else None
            if match:
                return int(match.group(1)), "config:local-model-config.yaml"
    except OSError:
        pass
    return None, "unavailable"


# ── measurement ─────────────────────────────────────────────────────────────

def _payload_bytes(payload: dict) -> int:
    """UTF-8 size of everything prompt-bearing in the request (messages, tool
    schemas, grammar). Every token is >= 1 byte, so this never undercounts."""
    parts = {k: payload[k] for k in _PROMPT_KEYS if payload.get(k)}
    parts.update(template_options(payload))
    return len(json.dumps(parts, ensure_ascii=False).encode("utf-8")) + FALLBACK_TEMPLATE_MARGIN_TOKENS


# Request fields llama.cpp's chat-template rendering consumes; forwarded verbatim so the
# measured prompt is rendered exactly as the real request will be.
TEMPLATE_KEYS = ("chat_template_kwargs", "tools", "tool_choice", "parallel_tool_calls",
                 "add_generation_prompt", "enable_thinking", "reasoning_format")


def template_options(payload: dict) -> dict:
    return {k: payload[k] for k in TEMPLATE_KEYS if payload.get(k) is not None}


def measure_payload(payload: dict, llama_url: str) -> tuple[int, str]:
    """(tokens, method) for the request exactly as it will be sent.

    Exact path: the server renders the chat template (/apply-template) and
    tokenizes that rendered prompt; tool schemas / grammar carried outside
    messages are added at their byte size (an upper bound). If either server
    call is unavailable the whole request falls back to bytes-as-tokens.
    """
    body: dict[str, Any] = {"messages": payload.get("messages", [])}
    body.update(template_options(payload))
    rendered = _http_json(f"{llama_url}/apply-template", body)
    prompt = rendered.get("prompt") if isinstance(rendered, dict) else None
    if isinstance(prompt, str):
        tok = _http_json(f"{llama_url}/tokenize",
                         {"content": prompt, "add_special": True, "parse_special": True})
        if isinstance(tok, dict) and isinstance(tok.get("tokens"), list):
            # apply-template already rendered messages (+ tools when sent). Only keys the
            # server renders into context but apply-template did not cover are added;
            # _tool_schemas (never sent; the system prompt lists tools) and grammar /
            # json_schema (sampler constraints) are not context.
            extras = {k: payload[k] for k in ("response_format",) if payload.get(k)}
            extra_bytes = len(json.dumps(extras, ensure_ascii=False).encode("utf-8")) if extras else 0
            return len(tok["tokens"]) + extra_bytes, "apply_template+tokenize"
    return _payload_bytes(payload), "byte_upper_bound"


def preflight(payload: dict, max_tokens: int, llama_url: str, mode: str) -> dict:
    """Verdict dict: {method, measured, limit, verdict, ...}. Pure; no side effects.

    `payload` is the request the runner would POST (build_llama_payload output).
    """
    limit, limit_source = context_limit(llama_url)
    prompt_tokens, method = measure_payload(payload, llama_url)
    measured = prompt_tokens + int(max_tokens)
    result: dict[str, Any] = {
        "method": method,
        "measured": measured,
        "prompt_tokens": prompt_tokens,
        "output_allowance": int(max_tokens),
        "limit": limit,
        "limit_source": limit_source,
        "mode": mode,
        "overhead": "rendered_request:template+tools",
    }
    if limit is None:
        # Fail closed: without a context limit nothing can be proven to fit.
        result["verdict"] = "refuse"
        result["reason"] = "no_context_limit"
        result["terminal_reason"] = "preflight_no_limit"
        result["decompose_hint"] = ("No context limit is available (llama /props unreachable and "
                                    "no inference.ctx_size in config/local-model-config.yaml); "
                                    "restore the limit source and retry.")
    elif measured > limit:
        result["verdict"] = "refuse"
        result["reason"] = "assembled_prompt_plus_output_exceeds_context"
        result["decompose_hint"] = (
            f"Split into slices whose prompt fits in <= {max(limit - int(max_tokens), 0)} tokens "
            "(or lower --max-tokens); pass file paths instead of inlined content.")
    else:
        result["verdict"] = "accept"
    return result


def output_budget_preflight(max_tokens: int, llama_url: str, mode: str) -> Optional[dict]:
    """Prompt-independent refusal: None unless the output budget alone cannot fit.

    An explicit output allowance >= the context limit cannot fit whatever the prompt is,
    so callers may refuse before classification and prompt assembly. A missing limit
    refuses exactly as preflight() does (fail closed).
    """
    limit, limit_source = context_limit(llama_url)
    result: dict[str, Any] = {
        "method": "output_budget_only", "measured": int(max_tokens), "prompt_tokens": None,
        "output_allowance": int(max_tokens), "limit": limit, "limit_source": limit_source,
        "mode": mode, "overhead": "none:prompt_not_measured",
    }
    if limit is None:
        result.update(verdict="refuse", reason="no_context_limit", terminal_reason="preflight_no_limit",
                      decompose_hint=("No context limit is available (llama /props unreachable and "
                                      "no inference.ctx_size in config/local-model-config.yaml); "
                                      "restore the limit source and retry."))
        return result
    if int(max_tokens) >= limit:
        result.update(verdict="refuse", reason="output_budget_exceeds_context",
                      decompose_hint=f"Lower --max-tokens below the context limit ({limit}) "
                                     "and split the work so prompt plus output fits.")
        return result
    return None


NOT_MEASURED_LIMITATION = "service-side assembly not measurable at dispatch"


def not_measured(mode: str) -> dict:
    """Labeled limitation for modes whose prompt is assembled by a remote service."""
    return {"method": "n/a", "measured": None, "limit": None, "verdict": "not_measured",
            "mode": mode, "limitation": NOT_MEASURED_LIMITATION}


def refusal_json(task_id: str, pf: dict) -> str:
    return json.dumps({
        "refused": True, "task_id": task_id, "reason": pf.get("reason"),
        "measured": pf.get("measured"), "limit": pf.get("limit"),
        "method": pf.get("method"), "limit_source": pf.get("limit_source"),
        "decompose_hint": pf.get("decompose_hint"), "exit_code": PREFLIGHT_EXIT_CODE,
    })


# ── observability ───────────────────────────────────────────────────────────

def summarize(entries: list[dict], recent: int = 5) -> dict:
    """Dispatch coverage by source + local refusals, unknowns kept visible."""
    by_source: dict[str, int] = {}
    with_evidence = 0
    refusals = []
    verdicts: dict[str, int] = {}
    for e in entries:
        by_source[str(e.get("source") or "unrecorded")] = by_source.get(str(e.get("source") or "unrecorded"), 0) + 1
        if "dispatch_id" in e:
            with_evidence += 1
        pf = e.get("preflight")
        if isinstance(pf, dict):
            v = str(pf.get("verdict"))
            verdicts[v] = verdicts.get(v, 0) + 1
            if v == "refuse":
                refusals.append({"id": e.get("id"), "created": e.get("created"),
                                 "measured": pf.get("measured"), "limit": pf.get("limit"),
                                 "method": pf.get("method")})
    return {
        "total": len(entries),
        "with_normalized_evidence": with_evidence,
        "without_normalized_evidence": len(entries) - with_evidence,
        "by_source": by_source,
        "preflight_verdicts": verdicts,
        "local_refusals": len(refusals),
        "recent_refusals": refusals[-recent:],
    }
