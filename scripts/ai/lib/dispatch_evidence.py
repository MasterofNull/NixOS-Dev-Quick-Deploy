#!/usr/bin/env python3
"""Normalized dispatch evidence + local context preflight (routing slice S1).

Two concerns, one module because both feed the same registry row:

* normalize_row(): additive evidence fields for every delegate-to-* registry
  row. Existing keys are never overwritten; unknown values are the literal
  "unknown"/"n/a", never inferred.
* preflight(): measure the assembled local prompt + output allowance against
  the live model context limit BEFORE inference starts.

Context limit SSOT: the running llama-server (/props n_ctx / total_slots),
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
LOCAL_MODEL_CONFIG = REPO_ROOT / "config" / "local-model-config.yaml"

# Fallback only when /tokenize is unreachable. Over-counts on purpose
# (typical code/English is ~3-4 bytes/token); labeled method="byte_guard".
BYTES_PER_TOKEN_GUARD = float(os.environ.get("AQ_PREFLIGHT_BYTES_PER_TOKEN", "2"))
# Chat-template framing per message (role markers, end tokens).
PER_MESSAGE_OVERHEAD_TOKENS = int(os.environ.get("AQ_PREFLIGHT_MSG_OVERHEAD_TOKENS", "8"))
PREFLIGHT_EXIT_CODE = 3

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
    out = dict(row)
    for key, value in defaults.items():
        out.setdefault(key, value)
    return out


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
        slots = props.get("total_slots") or 1
        if isinstance(n_ctx, int) and n_ctx > 0:
            return n_ctx // max(int(slots), 1), "llama_props"
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

def measure_messages(messages: list[dict], llama_url: str) -> tuple[int, str]:
    """(tokens, method) for the assembled chat messages."""
    texts = [str(m.get("content") or "") for m in messages]
    framing = PER_MESSAGE_OVERHEAD_TOKENS * len(messages)
    tok = _http_json(f"{llama_url}/tokenize", {"content": "\n".join(texts)})
    if isinstance(tok, dict) and isinstance(tok.get("tokens"), list):
        return len(tok["tokens"]) + framing, "tokenize"
    size = sum(len(t.encode("utf-8")) for t in texts)
    return math.ceil(size / BYTES_PER_TOKEN_GUARD) + framing, "byte_guard"


def preflight(messages: list[dict], max_tokens: int, llama_url: str, mode: str) -> dict:
    """Verdict dict: {method, measured, limit, verdict, ...}. Pure; no side effects."""
    limit, limit_source = context_limit(llama_url)
    prompt_tokens, method = measure_messages(messages, llama_url)
    measured = prompt_tokens + int(max_tokens)
    result: dict[str, Any] = {
        "method": method,
        "measured": measured,
        "prompt_tokens": prompt_tokens,
        "output_allowance": int(max_tokens),
        "limit": limit,
        "limit_source": limit_source,
        "overhead": "template_framing" if mode == "direct" else "template_framing;agent_tool_schema_excluded",
    }
    if limit is None:
        result["verdict"] = "skipped_no_limit"
    elif measured > limit:
        result["verdict"] = "refuse"
        result["reason"] = "assembled_prompt_plus_output_exceeds_context"
        result["decompose_hint"] = (
            f"Split into slices whose prompt fits in <= {max(limit - int(max_tokens), 0)} tokens "
            "(or lower --max-tokens); pass file paths instead of inlined content.")
    else:
        result["verdict"] = "accept"
    return result


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
