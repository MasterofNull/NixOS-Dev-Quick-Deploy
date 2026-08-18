#!/usr/bin/env python3
"""
decompose_loop.py — DECOMPOSE-CONDENSE loop for over-budget local-model tasks.

Local Qwen3-35B has a small input budget (~5,200 tokens, see llm_config.py
budget math). Tasks larger than that budget cannot be handed to the model as
a single call. This module splits an over-budget task into ORDERED,
single-concern bites sized to fit the local model's window, then runs each
bite through the local model with per-bite semantic recall of prior bites'
results via the PROVEN embed-backed context_cache module (embed :8081 +
Qdrant :6333) — the "condense" half of decompose-condense: Qwen generates,
the embed model + Qdrant recall.

Reuses (does NOT reimplement):
  - context_cache.py: cache_evicted / retrieve_ctx / scratchpad_message.
    Fail-open by construction (embed/Qdrant down -> [] / None, never raises).
  - llm_config.py: build_llama_payload — SSOT for local LLM payload
    construction (MICRO fable-parity injection, enable_thinking nesting,
    task profiles). The production call_local wrapper (make_local_caller)
    builds its payload through this function; nothing here hand-rolls a
    llama.cpp payload.

Design:
  decompose() is a pure, deterministic function — no I/O, no model calls,
  structure-aware (headers / steps / fenced code kept intact where possible).

  run_decomposed() is the loop: retrieve -> assemble -> call -> cache -> repeat.
  Fail-open at every step: a failed bite is recorded in failed_bites and the
  loop CONTINUES to the next bite. run_decomposed() itself never raises.

Char/token heuristic: 4 chars/token — same convention already used in
agent_executor.py's context-guard (`_CTX_CHAR_BUDGET = 12000  # ~3000 tokens`).
This is an estimate, not a tokenizer call — deliberately cheap (minimal-code).
"""
from __future__ import annotations

import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx

# shared/ lives at ai-stack/mcp-servers/shared/ — mirrors agent_executor.py's
# sys.path setup so build_llama_payload stays the single source of truth for
# local LLM payloads (this module never hand-rolls a payload dict).
_MCP_SERVERS_PATH = str(Path(__file__).resolve().parents[1] / "mcp-servers")
if _MCP_SERVERS_PATH not in sys.path:
    sys.path.insert(0, _MCP_SERVERS_PATH)

from shared.llm_config import build_llama_payload  # noqa: E402

# context_cache.py lives in this same directory. Fail-open import (mirrors
# agent_executor.py's pattern): a missing/broken cache module must never break
# the decompose loop — it only disables per-bite semantic recall, bites still
# run without cross-bite retrieval.
_THIS_DIR = str(Path(__file__).resolve().parent)
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
try:
    import context_cache  # noqa: E402  (same dir: ai-stack/local-agents/)
except Exception:  # noqa: BLE001 — optional import, never break the loop
    context_cache = None  # type: ignore


# ---------------------------------------------------------------------------
# Token estimate — 4 chars/token, matches agent_executor.py's context-guard.
# ---------------------------------------------------------------------------
_CHARS_PER_TOKEN = 4


def _estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, math.ceil(len(text) / _CHARS_PER_TOKEN))


DEFAULT_MAX_BITE_TOKENS = 1200
DEFAULT_BUDGET_TOKENS = 5200
DEFAULT_RETRIEVAL_K = 6

# Compact framing for a single bite — deliberately short (this is not the
# Fable-parity MICRO block; that is auto-injected by build_llama_payload in
# the production call_local wrapper via task_type, per llm_config.py SSOT).
_BITE_SYSTEM_PROMPT = (
    "You are completing one bounded slice of a larger task that was split "
    "into ordered bites because it did not fit in one context window. "
    "Answer only this bite; do not restate the whole task. Be concise."
)

_SYNTHESIS_SYSTEM_PROMPT = (
    "The following are per-bite results from a task that was decomposed "
    "into ordered bites and run separately. Synthesize them into one "
    "coherent final answer. Do not repeat bite labels or restate the "
    "process — produce the final answer only."
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Bite:
    """One ordered, single-concern slice of an over-budget task."""
    index: int
    text: str
    query: str  # short string used to drive per-bite context_cache retrieval


@dataclass
class BiteResult:
    index: int
    query: str
    output: str
    tokens_estimate: int


@dataclass
class FailedBite:
    index: int
    query: str
    error: str


@dataclass
class Result:
    final: str
    bites: List[BiteResult] = field(default_factory=list)
    failed_bites: List[FailedBite] = field(default_factory=list)
    collection: Optional[str] = None
    token_stats: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# decompose() — structure-aware, deterministic splitting
# ---------------------------------------------------------------------------
_HEADER_RE = re.compile(r"^#{1,6}\s+\S.*$", re.MULTILINE)
_STEP_RE = re.compile(r"^[ \t]*(?:\d+[.)][ \t]+|[-*][ \t]+)\S", re.MULTILINE)
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


def _split_by_marker_regex(text: str, marker_re: "re.Pattern") -> List[str]:
    """Split text into blocks starting at each regex match (header / step
    marker), each block running up to the next match. Any content before the
    first match (a preamble) becomes its own leading block. A single/zero
    match returns [text] unchanged — caller falls through to the next
    splitting strategy."""
    matches = list(marker_re.finditer(text))
    if len(matches) < 2:
        return [text]
    parts: List[str] = []
    if matches[0].start() > 0:
        pre = text[: matches[0].start()]
        if pre.strip():
            parts.append(pre)
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts.append(text[start:end])
    return parts


def _split_paragraphs_fence_aware(text: str) -> List[str]:
    """Split on blank lines, but never split inside a ``` fenced code block —
    this is the 'files' half of 'sections/steps/files': a file's fenced
    contents stay together as one unit unless it alone exceeds budget."""
    lines = text.split("\n")
    paras: List[str] = []
    current: List[str] = []
    in_fence = False
    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            current.append(line)
            continue
        if not in_fence and line.strip() == "" and current:
            paras.append("\n".join(current))
            current = []
        else:
            current.append(line)
    if current:
        paras.append("\n".join(current))
    return [p for p in paras if p.strip()]


def _hard_split(text: str, max_tokens: int) -> List[str]:
    """Last-resort split on whitespace boundaries at max_tokens*4 chars.
    Only reached when a single sentence/line alone exceeds the bite budget."""
    max_chars = max(1, max_tokens * _CHARS_PER_TOKEN)
    chunks: List[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break
        cut = remaining.rfind(" ", 0, max_chars)
        if cut <= 0:
            cut = max_chars
        chunks.append(remaining[:cut])
        remaining = remaining[cut:].lstrip()
    return chunks


def _shrink_unit(text: str, max_tokens: int) -> List[str]:
    """Recursively split one oversized unit: step markers, then sentences,
    then a hard char split. Returns pieces each <= max_tokens (best-effort;
    a single unbroken token-less blob still gets hard-split)."""
    if _estimate_tokens(text) <= max_tokens:
        return [text]

    step_pieces = _split_by_marker_regex(text, _STEP_RE)
    if len(step_pieces) > 1:
        out: List[str] = []
        for piece in step_pieces:
            out.extend(_shrink_unit(piece, max_tokens))
        return out

    sentences = [s for s in _SENTENCE_RE.split(text) if s.strip()]
    if len(sentences) > 1:
        out = []
        for sentence in sentences:
            out.extend(_shrink_unit(sentence, max_tokens))
        return out

    return _hard_split(text, max_tokens)


def _pack_by_tokens(pieces: List[str], max_tokens: int, joiner: str = "\n\n") -> List[str]:
    """Greedily bin-pack ordered pieces into groups <= max_tokens, preserving
    order. A single oversized piece is hard-split rather than dropped. Checks
    the exact joined-string token estimate (not a running per-piece sum) so
    the joiner's own chars are never silently uncounted."""
    groups: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            groups.append(joiner.join(current))
            current.clear()

    for piece in pieces:
        if not piece.strip():
            continue
        if _estimate_tokens(piece) > max_tokens:
            flush()
            groups.extend(_hard_split(piece, max_tokens))
            continue
        candidate_tokens = _estimate_tokens(joiner.join(current + [piece])) if current else _estimate_tokens(piece)
        if current and candidate_tokens > max_tokens:
            flush()
        current.append(piece)
    flush()
    return groups


def _derive_query(bite_text: str, limit: int = 200) -> str:
    """Short string driving context_cache retrieval for this bite — the
    first non-empty line (usually a header/step marker), else a char prefix."""
    for line in bite_text.splitlines():
        line = line.strip()
        if line:
            return line[:limit]
    return bite_text[:limit]


def decompose(task_text: str, max_bite_tokens: int = DEFAULT_MAX_BITE_TOKENS) -> List[Bite]:
    """Split an over-budget task into ORDERED, single-concern bites sized to
    fit max_bite_tokens. Deterministic, structure-aware: prefers splitting on
    markdown headers, then numbered/bulleted steps, then fenced-code-aware
    paragraphs, only falling to sentence/hard splits when a single unit alone
    exceeds budget. A task that already fits returns exactly one Bite
    (no-op) with its original text unchanged."""
    text = task_text or ""
    if not text.strip():
        return []
    if _estimate_tokens(text) <= max_bite_tokens:
        return [Bite(index=0, text=text, query=_derive_query(text))]

    header_sections = _split_by_marker_regex(text, _HEADER_RE)
    units: List[str] = []
    for section in header_sections:
        for para in _split_paragraphs_fence_aware(section):
            units.extend(_shrink_unit(para, max_bite_tokens))

    if not units:
        units = _shrink_unit(text, max_bite_tokens)

    groups = _pack_by_tokens(units, max_bite_tokens, joiner="\n\n")
    if not groups:
        # Degenerate input (e.g. only whitespace survived splitting) — treat
        # as a single bite rather than returning nothing for non-empty input.
        return [Bite(index=0, text=text, query=_derive_query(text))]
    return [Bite(index=i, text=g, query=_derive_query(g)) for i, g in enumerate(groups)]


# ---------------------------------------------------------------------------
# Per-bite prompt assembly — retrieved context, trimmed to fit budget_tokens.
# ---------------------------------------------------------------------------
def _assemble_prompt(bite: Bite, retrieved: List[str], budget_tokens: int) -> tuple:
    """Build the message list for one bite: framing system message + the
    retrieved-context scratchpad (context_cache.scratchpad_message, appended
    AFTER the system message per its KV-safe placement contract) + the bite
    itself. retrieve_ctx() returns hits in relevance order (best first), so
    when over budget_tokens we drop the LOWEST-relevance chunk first (from
    the end) and re-check, until it fits or nothing is left to drop.

    Returns (messages, retrieved_used).
    """
    remaining = list(retrieved or [])
    while True:
        messages: List[Dict[str, str]] = [{"role": "system", "content": _BITE_SYSTEM_PROMPT}]
        scratch = None
        if context_cache is not None and remaining:
            try:
                scratch = context_cache.scratchpad_message(remaining)
            except Exception:
                scratch = None
        if scratch:
            messages.append(scratch)
        messages.append({"role": "user", "content": bite.text})

        total = sum(_estimate_tokens(m.get("content") or "") for m in messages)
        if total <= budget_tokens or not remaining:
            return messages, remaining
        remaining = remaining[:-1]  # drop lowest-relevance (last) chunk, retry


# ---------------------------------------------------------------------------
# Synthesis — final local call over condensed results, or deterministic
# concatenation fallback if that call is over budget or fails.
# ---------------------------------------------------------------------------
def _synthesize(
    bite_results: List[BiteResult],
    call_local: Callable[[List[Dict[str, str]]], Any],
    budget_tokens: int,
) -> str:
    if not bite_results:
        return ""
    if len(bite_results) == 1:
        return bite_results[0].output

    condensed = "\n\n".join(f"[Bite {r.index}] {r.output}" for r in bite_results)
    synth_messages = [
        {"role": "system", "content": _SYNTHESIS_SYSTEM_PROMPT},
        {"role": "user", "content": condensed},
    ]
    synth_tokens = sum(_estimate_tokens(m["content"]) for m in synth_messages)

    if synth_tokens <= budget_tokens:
        try:
            output = call_local(synth_messages)
            if output and isinstance(output, str) and output.strip():
                return output
        except Exception:
            pass  # fail-open: fall through to deterministic concatenation

    # Deterministic fallback — over budget for a model call, or the call
    # itself failed. Never lose the per-bite work.
    return condensed


# ---------------------------------------------------------------------------
# run_decomposed() — the decompose-condense loop
# ---------------------------------------------------------------------------
def run_decomposed(
    task_text: str,
    *,
    task_id: str,
    call_local: Callable[[List[Dict[str, str]]], Any],
    max_bite_tokens: int = DEFAULT_MAX_BITE_TOKENS,
    budget_tokens: int = DEFAULT_BUDGET_TOKENS,
    retrieval_k: int = DEFAULT_RETRIEVAL_K,
) -> Result:
    """Run an over-budget task through the local model as ordered bites, with
    per-bite semantic recall of prior bites' results via context_cache.

    call_local(messages) -> str is injected so production wires it to a thin
    build_llama_payload -> :8080 wrapper (see make_local_caller below) while
    tests stub it directly. call_local may raise or return empty/None; either
    is treated as a bite failure — recorded in Result.failed_bites, loop
    continues. run_decomposed() itself never raises.
    """
    bites = decompose(task_text, max_bite_tokens=max_bite_tokens)
    token_stats: Dict[str, Any] = {
        "bite_count": len(bites),
        "max_bite_tokens": max_bite_tokens,
        "budget_tokens": budget_tokens,
        "prompt_tokens_by_bite": [],
        "output_tokens_by_bite": [],
    }
    if not bites:
        return Result(final="", token_stats=token_stats)

    bite_results: List[BiteResult] = []
    failed_bites: List[FailedBite] = []
    collection: Optional[str] = None

    for bite in bites:
        retrieved: List[str] = []
        if context_cache is not None and collection:
            try:
                retrieved = context_cache.retrieve_ctx(collection, bite.query, k=retrieval_k) or []
            except Exception:
                retrieved = []

        messages, _used = _assemble_prompt(bite, retrieved, budget_tokens)
        prompt_tokens = sum(_estimate_tokens(m.get("content") or "") for m in messages)
        token_stats["prompt_tokens_by_bite"].append(prompt_tokens)

        try:
            output = call_local(messages)
            if output is None or (isinstance(output, str) and not output.strip()):
                raise RuntimeError("empty response from local model")
        except Exception as exc:  # noqa: BLE001 — fail-open, per-bite resilience
            failed_bites.append(FailedBite(index=bite.index, query=bite.query, error=str(exc)[:300]))
            token_stats["output_tokens_by_bite"].append(0)
            continue

        output_text = output if isinstance(output, str) else str(output)
        tokens_out = _estimate_tokens(output_text)
        token_stats["output_tokens_by_bite"].append(tokens_out)
        bite_results.append(
            BiteResult(index=bite.index, query=bite.query, output=output_text, tokens_estimate=tokens_out)
        )

        # Accumulation: cache this bite's result so LATER bites can recall it.
        if context_cache is not None:
            try:
                cache_chunk = f"[Bite {bite.index}] {bite.query}\n{output_text}"
                new_collection = context_cache.cache_evicted(task_id, [cache_chunk])
                if new_collection:
                    collection = new_collection
            except Exception:
                pass  # fail-open — this bite's result just won't be recallable later

    final = _synthesize(bite_results, call_local, budget_tokens)
    token_stats["failed_count"] = len(failed_bites)
    token_stats["completed_count"] = len(bite_results)
    return Result(
        final=final,
        bites=bite_results,
        failed_bites=failed_bites,
        collection=collection,
        token_stats=token_stats,
    )


# ---------------------------------------------------------------------------
# Production call_local — thin wrapper over build_llama_payload -> :8080.
# Tests inject their own stub instead of this; this is what a real caller
# (e.g. agent_executor or a CLI entry point) passes as call_local=.
# ---------------------------------------------------------------------------
def make_local_caller(
    llama_endpoint: Optional[str] = None,
    task_type: str = "code",
    timeout: float = 300.0,
) -> Callable[[List[Dict[str, str]]], str]:
    """Return a sync call_local(messages) -> str bound to a real llama.cpp
    endpoint, payloads built exclusively through build_llama_payload (SSOT —
    handles MICRO fable-parity injection, enable_thinking nesting, task
    profiles). Raises on transport/HTTP error; run_decomposed() catches that
    per-bite and records it in failed_bites — this wrapper does not need to
    be fail-open itself."""
    endpoint = llama_endpoint or os.environ.get(
        "LLAMA_CPP_URL", os.environ.get("LLAMA_URL", "http://127.0.0.1:8080")
    )

    def _call(messages: List[Dict[str, str]]) -> str:
        payload = build_llama_payload(messages, task_type=task_type)
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{endpoint}/v1/chat/completions", json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    return _call
