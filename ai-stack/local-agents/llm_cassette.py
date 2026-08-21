#!/usr/bin/env python3
"""
LLM record/replay cassette — deterministic, instant replay of local-agent inference.

Problem: every dogfood validation of the local-agent loop is a 30-40 min LIVE run on
the APU, subject to transient variance (silent-server-timeout, grammar drift, budget
exhaustion, etc). This module lets `_call_llama` in agent_executor.py record real model
outputs once, then replay them deterministically and offline — so harness fixes and
config A/Bs (grammar on/off, write_region, PTC) validate in seconds, not tens of minutes.

Design doc (authoritative): .agents/plans/record-replay-harness/DESIGN.md

Modes (env AQ_LLM_CASSETTE_MODE, default "off"):
    off            — no-op. Zero behavior change (the sacrosanct default).
    record         — live call happens; (key -> content, tokens) is appended to the
                     cassette at AQ_LLM_CASSETTE.
    replay         — NO network. Returns the cassette's recorded content for the
                     request's key. Miss behavior is AQ_LLM_CASSETTE_ON_MISS
                     (error [default] | passthrough | empty).
    replay-record  — replay on hit; live + record on miss (grows a cassette
                     incrementally).

Everything in this module is stdlib-only (hashlib/json/os) and fails SAFE: any
internal error (corrupt cassette line, unwritable path, etc) is logged and swallowed,
never propagated into the caller's live inference path. The one deliberate exception
is `ReplayMiss`, raised only when the operator has explicitly asked for
AQ_LLM_CASSETTE_ON_MISS=error (the default in `replay` mode) — that is a signal, not a
bug.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Fields considered part of the SEMANTIC request identity. Everything else in a
# build_llama_payload() dict (chat_template_kwargs, repeat_penalty, repeat_last_n,
# cache_prompt, stream_options, ...) is volatile/derived and deliberately excluded so
# the key is stable across runs that only differ in those knobs.
_SEMANTIC_FIELDS: Tuple[str, ...] = (
    "messages",
    "max_tokens",
    "temperature",
    "grammar",
    "task_type",
    "tools",
    "stream",
)


class ReplayMiss(Exception):
    """Raised in replay mode (AQ_LLM_CASSETTE_ON_MISS=error, the default) when no
    recorded row exists for the computed request key. Carries the key and a short
    payload summary so the failure is immediately actionable."""

    def __init__(self, key: str, payload: Optional[Dict[str, Any]] = None):
        self.key = key
        self.payload_summary = _summarize_payload(payload) if payload else ""
        super().__init__(
            f"llm_cassette: REPLAY MISS for key={key} — no recorded row. "
            f"payload={self.payload_summary}"
        )


def _summarize_payload(payload: Dict[str, Any]) -> str:
    try:
        messages = payload.get("messages") or []
        last = messages[-1] if messages else {}
        preview = str(last.get("content", ""))[:120].replace("\n", "\\n")
        return (
            f"max_tokens={payload.get('max_tokens')} "
            f"temperature={payload.get('temperature')} "
            f"n_messages={len(messages)} last='{preview}'"
        )
    except Exception:
        return "<unavailable>"


def _normalize_messages(messages: Any) -> List[Dict[str, Any]]:
    if not isinstance(messages, list):
        return []
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append({"role": m.get("role"), "content": m.get("content")})
    return out


def request_key(payload: Dict[str, Any], task_type: Optional[str] = None) -> str:
    """Stable sha256 over the SEMANTIC request only.

    Includes: messages (role+content), max_tokens, temperature, grammar, task_type,
    tools, stream. Excludes volatile fields (timestamps, request ids, cache flags,
    chat_template_kwargs, repeat_penalty/repeat_last_n, frequency_penalty, ...) so the
    same logical request hashes identically across runs and machines.

    `task_type` is accepted as a separate optional arg because build_llama_payload()
    consumes it as a keyword-only builder argument and does NOT carry it into the
    resulting payload dict — callers that have task_type as a local variable should
    pass it explicitly. If the payload dict already carries a "task_type" key (e.g. a
    cassette row payload_digest reconstruction), that value wins.
    """
    try:
        semantic: Dict[str, Any] = {
            "messages": _normalize_messages(payload.get("messages")),
            "max_tokens": payload.get("max_tokens"),
            "temperature": payload.get("temperature"),
            "grammar": payload.get("grammar"),
            "task_type": payload.get("task_type", task_type),
            "tools": payload.get("tools"),
            "stream": bool(payload.get("stream", False)),
        }
        blob = json.dumps(semantic, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
    except Exception:
        logger.exception("llm_cassette: request_key failed — this is a bug, not a miss")
        raise


class Cassette:
    """A JSONL-backed store of recorded (key -> content, tokens) rows.

    Multiple rows may share a key (the same request issued more than once in a run,
    e.g. a retry or a repeated planning step with identical semantic content). Rows are
    consumed in APPEND order per key via a per-instance cursor: the Nth lookup for a
    given key returns the Nth recorded row for that key, so a two-call sequence with an
    identical key replays its 1st call's output, then its 2nd.
    """

    def __init__(self, cassette_path: str):
        self.path = Path(cassette_path)
        self._rows: Optional[Dict[str, List[Dict[str, Any]]]] = None
        self._cursor: Dict[str, int] = {}

    def _load(self) -> None:
        if self._rows is not None:
            return
        rows: Dict[str, List[Dict[str, Any]]] = {}
        if self.path.exists():
            try:
                with self.path.open("r", encoding="utf-8") as fh:
                    for line_no, line in enumerate(fh, start=1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            logger.warning(
                                "llm_cassette: skipping corrupt row %s:%d", self.path, line_no
                            )
                            continue
                        key = row.get("key")
                        if not key:
                            continue
                        rows.setdefault(key, []).append(row)
            except OSError as e:
                logger.warning("llm_cassette: failed to read %s: %s", self.path, e)
        self._rows = rows

    def record(
        self,
        key: str,
        payload: Dict[str, Any],
        content: str,
        tokens: int,
        meta: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append one row. Never raises — logs and no-ops on any IO/serialization error."""
        try:
            payload_digest = hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
            ).hexdigest()
        except Exception:
            payload_digest = ""
        row = {
            "key": key,
            "payload_digest": payload_digest,
            "content": content,
            "tokens": tokens,
            "meta": meta or {},
            "ts": time.time(),
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError as e:
            logger.warning("llm_cassette: failed to write %s: %s", self.path, e)
            return
        # Keep the in-memory index in sync so a record()-then-lookup() in the same
        # process (replay-record mode, or a test) sees the row immediately without
        # re-reading the file.
        if self._rows is not None:
            self._rows.setdefault(key, []).append(row)

    def lookup(self, key: str) -> Optional[Tuple[str, int]]:
        """Return (content, tokens) for the next unconsumed row at this key, in
        call order, or None if no (further) row exists. Never raises."""
        try:
            self._load()
            assert self._rows is not None
            rows = self._rows.get(key)
            if not rows:
                return None
            idx = self._cursor.get(key, 0)
            if idx >= len(rows):
                return None
            row = rows[idx]
            self._cursor[key] = idx + 1
            return row.get("content", ""), int(row.get("tokens", 0) or 0)
        except Exception:
            logger.exception("llm_cassette: lookup failed for key=%s — treating as miss", key)
            return None

    def reset_cursor(self) -> None:
        """Rewind consumption cursors to the start (useful for re-running the same
        cassette against a second config in aq-replay-bench)."""
        self._cursor = {}


# ---------------------------------------------------------------------------
# Module-level env readers + a small per-path cassette cache so the consumption
# cursor persists across the many _call_llama invocations of a single task loop.
# ---------------------------------------------------------------------------

_VALID_MODES = ("off", "record", "replay", "replay-record")
_VALID_ON_MISS = ("error", "passthrough", "empty")

_cassette_cache: Dict[str, Cassette] = {}


def mode() -> str:
    m = os.environ.get("AQ_LLM_CASSETTE_MODE", "off").strip().lower()
    return m if m in _VALID_MODES else "off"


def path() -> Optional[str]:
    p = os.environ.get("AQ_LLM_CASSETTE")
    return p.strip() if p and p.strip() else None


def on_miss() -> str:
    o = os.environ.get("AQ_LLM_CASSETTE_ON_MISS", "error").strip().lower()
    return o if o in _VALID_ON_MISS else "error"


def get_cassette(cassette_path: Optional[str] = None) -> Optional[Cassette]:
    """Return the process-wide Cassette for `cassette_path` (or AQ_LLM_CASSETTE if
    omitted), creating it on first use. Returns None if no path is configured."""
    p = cassette_path if cassette_path is not None else path()
    if not p:
        return None
    resolved = str(Path(p).expanduser())
    cass = _cassette_cache.get(resolved)
    if cass is None:
        cass = Cassette(resolved)
        _cassette_cache[resolved] = cass
    return cass


def reset_cache() -> None:
    """Test/bench helper: drop all cached Cassette instances (and their cursors)."""
    _cassette_cache.clear()


# ---------------------------------------------------------------------------
# Orchestration helpers — the thin surface agent_executor._call_llama wires into.
# Both are pure no-ops in mode "off" and fail safe (fall through to live) on any
# internal error, per the design's guardrail.
# ---------------------------------------------------------------------------

def replay_lookup(
    payload: Dict[str, Any], task_type: Optional[str] = None
) -> Optional[Tuple[str, int]]:
    """Consult the cassette in replay/replay-record modes.

    Returns:
        (content, tokens) on a cassette hit, or on-miss "empty" policy.
        None — proceed with the live call — in mode "off"/"record", on a
              replay-record miss, or on-miss "passthrough".
    Raises:
        ReplayMiss — mode "replay", on-miss "error" (the default), and no row exists.
    """
    m = mode()
    if m not in ("replay", "replay-record"):
        return None
    try:
        cass = get_cassette()
        if cass is None:
            logger.warning(
                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — proceeding live", m
            )
            return None
        key = request_key(payload, task_type)
        hit = cass.lookup(key)
    except ReplayMiss:
        raise
    except Exception:
        logger.exception("llm_cassette: replay_lookup internal error — falling back to live")
        return None

    if hit is not None:
        return hit

    if m == "replay-record":
        return None  # fall through to live; caller records after

    policy = on_miss()
    if policy == "passthrough":
        return None
    if policy == "empty":
        return "", 0
    # policy == "error" (default): a miss in strict replay mode is a test failure.
    raise ReplayMiss(key, payload)


def maybe_record(
    payload: Dict[str, Any],
    task_type: Optional[str],
    content: str,
    tokens: int,
    meta: Optional[Dict[str, Any]] = None,
) -> None:
    """Tee a live (content, tokens) result into the cassette in record/replay-record
    modes. No-op in off/replay. Never raises."""
    m = mode()
    if m not in ("record", "replay-record"):
        return
    try:
        cass = get_cassette()
        if cass is None:
            logger.warning(
                "llm_cassette: mode=%s but AQ_LLM_CASSETTE is unset — not recording", m
            )
            return
        key = request_key(payload, task_type)
        cass.record(key, payload, content, tokens, meta)
    except Exception:
        logger.exception("llm_cassette: maybe_record internal error — continuing without recording")
