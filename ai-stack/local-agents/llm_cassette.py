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

Everything in this module is stdlib-only (hashlib/json/os) and fails SAFE for
RECORDING (a write-side error never breaks the caller's live inference path). REPLAY
is the opposite: it fails CLOSED. Replay's entire value proposition is "no network" —
so a broken replay configuration (bad mode string, missing cassette path, a corrupt
lookup, a key hit whose full payload digest doesn't match) must never silently
degrade to a live call, because that would mask a real regression as a false pass.
The deliberate hard-error exceptions are `ReplayMiss` (no recorded row for a strict
lookup), `ReplayConfigError` (misconfiguration / internal replay failure), and
`ReplayDigestMismatch` (a key matched but the full payload differs) — none of these
are ever swallowed on the replay path. Live fallback on a clean miss is permitted
ONLY under the explicitly-named `replay-record` mode or an `on_miss=passthrough`
policy — both are opt-in, never a silent default.
"""

from __future__ import annotations

import hashlib
import contextvars
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import fcntl
except ImportError:  # pragma: no cover — non-POSIX platform; record() fails safe below.
    fcntl = None  # type: ignore

logger = logging.getLogger(__name__)

# Fields considered part of the SEMANTIC/behavioral request identity — everything
# that can change what the model actually generates. Hashed into request_key().
# Anything NOT in this list (cache_prompt, repeat_last_n, stream_options, ...) is a
# perf/transport knob that never changes model output and is deliberately excluded
# so the key stays stable across runs that only differ in those. NOTE: the full raw
# payload (including those excluded knobs) is separately hashed into payload_digest
# and verified on every lookup (see Cassette.lookup) as a belt-and-suspenders check
# against any field this list fails to anticipate.
_SEMANTIC_FIELDS: Tuple[str, ...] = (
    "model",
    "messages",
    "max_tokens",
    "temperature",
    "grammar",
    "task_type",
    "tools",
    "stream",
    "enable_thinking",
    "thinking_budget",
    "frequency_penalty",
    "repeat_penalty",
    "stop",
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


class ReplayConfigError(Exception):
    """Raised when the cassette is being used in an active replay/replay-record
    context but is unusable: an explicitly-set but unrecognized AQ_LLM_CASSETTE_MODE
    string, a missing AQ_LLM_CASSETTE path, or an internal lookup error. Fail-closed
    by design — a broken replay configuration must error loudly, never silently fall
    back to a live call (that would defeat replay's "no network" guarantee and mask
    a real regression as a false pass)."""


class ReplayDigestMismatch(Exception):
    """Raised when a cassette row's request_key() matches the live request but its
    stored full-payload digest does NOT — some field outside the curated semantic
    set differs between record-time and replay-time. Silently replaying here risks
    returning a response recorded for a subtly different request; this is a hard
    error, never swallowed on the replay path."""

    def __init__(self, key: str, stored_digest: str, live_digest: str):
        self.key = key
        self.stored_digest = stored_digest
        self.live_digest = live_digest
        super().__init__(
            f"llm_cassette: PAYLOAD DIGEST MISMATCH for key={key} — cassette row "
            f"digest {stored_digest[:12]}... != live request digest {live_digest[:12]}... "
            "(request_key()'s canonical fields matched but the full payload differs — "
            "refusing to replay a possibly-wrong response)."
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
    """Full behavioral message identity: role+content+name+tool_call_id. name/
    tool_call_id are included (as None when absent) because a tool-result message's
    identity depends on which tool/call it answers — two otherwise-identical
    conversations that differ only in which tool a result came from are DIFFERENT
    requests and must not collide on the same cassette key."""
    if not isinstance(messages, list):
        return []
    out = []
    for m in messages:
        if isinstance(m, dict):
            out.append({
                "role": m.get("role"),
                "content": m.get("content"),
                "name": m.get("name"),
                "tool_call_id": m.get("tool_call_id"),
            })
    return out


def request_key(payload: Dict[str, Any], task_type: Optional[str] = None) -> str:
    """Stable sha256 over the COMPLETE canonical behavioral request.

    Includes: model (if present), messages (role+content+name+tool_call_id),
    max_tokens, temperature, grammar, task_type, tools, stream,
    chat_template_kwargs.enable_thinking/thinking_budget, frequency_penalty,
    repeat_penalty, stop. Excludes only genuinely non-semantic fields (cache_prompt,
    repeat_last_n, stream_options, request ids, timestamps) that never change what
    the model generates. See Cassette.lookup()'s payload_digest verification for a
    belt-and-suspenders check against anything this list fails to anticipate.

    `task_type` is accepted as a separate optional arg because build_llama_payload()
    consumes it as a keyword-only builder argument and does NOT carry it into the
    resulting payload dict — callers that have task_type as a local variable should
    pass it explicitly. If the payload dict already carries a "task_type" key (e.g. a
    cassette row payload_digest reconstruction), that value wins.
    """
    try:
        ctk = payload.get("chat_template_kwargs") or {}
        semantic: Dict[str, Any] = {
            "model": payload.get("model"),
            "messages": _normalize_messages(payload.get("messages")),
            "max_tokens": payload.get("max_tokens"),
            "temperature": payload.get("temperature"),
            "grammar": payload.get("grammar"),
            "task_type": payload.get("task_type", task_type),
            "tools": payload.get("tools"),
            "stream": bool(payload.get("stream", False)),
            "enable_thinking": ctk.get("enable_thinking"),
            "thinking_budget": ctk.get("thinking_budget"),
            "frequency_penalty": payload.get("frequency_penalty"),
            "repeat_penalty": payload.get("repeat_penalty"),
            "stop": payload.get("stop"),
        }
        blob = json.dumps(semantic, sort_keys=True, default=str, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
    except Exception:
        logger.exception("llm_cassette: request_key failed — this is a bug, not a miss")
        raise


def _payload_digest(payload: Dict[str, Any]) -> str:
    """sha256 over the FULL raw payload dict (every field, as literally passed) —
    the belt-and-suspenders check verified in Cassette.lookup() alongside the
    curated request_key(). Never raises; callers treat an empty string as
    "digest unavailable" (skip verification rather than false-positive fail)."""
    try:
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    except Exception:
        logger.exception("llm_cassette: _payload_digest failed — skipping digest verification")
        return ""


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
        """Append one row. Never raises — logs and no-ops on any IO/serialization error.

        The append itself is guarded with an exclusive fcntl.flock() so concurrent
        writers (e.g. parallel record runs) never interleave partial JSON lines into
        the same file. POSIX-only; fails safe (writes unlocked, logged) if fcntl is
        unavailable or flock() itself errors — a missing lock degrades to the old
        best-effort behavior rather than losing the recording entirely.
        """
        payload_digest = _payload_digest(payload)
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
                _locked = False
                if fcntl is not None:
                    try:
                        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
                        _locked = True
                    except OSError as e:
                        logger.warning(
                            "llm_cassette: flock unavailable for %s (%s) — writing unlocked", self.path, e
                        )
                try:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
                finally:
                    if _locked:
                        try:
                            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
                        except OSError:
                            pass
        except OSError as e:
            logger.warning("llm_cassette: failed to write %s: %s", self.path, e)
            return
        # Keep the in-memory index in sync so a record()-then-lookup() in the same
        # process (replay-record mode, or a test) sees the row immediately without
        # re-reading the file.
        if self._rows is not None:
            self._rows.setdefault(key, []).append(row)

    def lookup(
        self, key: str, payload: Optional[Dict[str, Any]] = None
    ) -> Optional[Tuple[str, int]]:
        """Return (content, tokens) for the next unconsumed row at this key, in
        call order, or None if no (further) row exists.

        When `payload` is given, the row's stored payload_digest is verified
        against a fresh digest of the live payload — a mismatch means
        request_key()'s curated field list matched but the full request differs in
        some other way, and raises ReplayDigestMismatch (a deliberate hard error,
        NOT swallowed by the generic except below). Everything else about this
        method stays fail-safe: an unrelated internal error is logged and treated
        as a miss, same as before.
        """
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
            if payload is not None:
                stored_digest = row.get("payload_digest") or ""
                live_digest = _payload_digest(payload)
                if stored_digest and live_digest and stored_digest != live_digest:
                    raise ReplayDigestMismatch(key, stored_digest, live_digest)
            self._cursor[key] = idx + 1
            return row.get("content", ""), int(row.get("tokens", 0) or 0)
        except ReplayDigestMismatch:
            raise
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
CASSETTE_FORMAT_VERSION = 2
_TOOL_OUTPUT_MAX_CHARS = 3000
_TOOL_EVIDENCE_PENDING: contextvars.ContextVar[Tuple[Dict[str, str], ...]] = (
    contextvars.ContextVar("llm_cassette_tool_evidence_pending", default=())
)
_SECRET_PATTERN = re.compile(r"(?i)(?:bearer\s+|aws_access_key_id|api[_-]?key|secret[_-]?key)[A-Za-z0-9_./+=:-]{8,}")


def normalize_tool_output_evidence(evidence: Any) -> Optional[Dict[str, str]]:
    """Validate closed, bounded, digest-bound, non-secret tool evidence."""
    if not isinstance(evidence, dict) or set(evidence) != {
        "tool_name", "result_content", "result_digest"
    }:
        return None
    tool_name = evidence.get("tool_name")
    content = evidence.get("result_content")
    digest = evidence.get("result_digest")
    if (not isinstance(tool_name, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", tool_name)
            or not isinstance(content, str) or not content
            or len(content) > _TOOL_OUTPUT_MAX_CHARS
            or _SECRET_PATTERN.search(content)
            or not isinstance(digest, str)
            or hashlib.sha256(content.encode("utf-8")).hexdigest() != digest):
        return None
    return {"tool_name": tool_name, "result_content": content, "result_digest": digest}


def record_formatted_tool_result(tool_name: str, formatted_result: str) -> None:
    """Queue the exact post-format tool result for the next recorded LLM turn.

    Unsafe, over-bound, or malformed output is deliberately omitted; mock replay then
    fails closed rather than storing or replaying a possibly sensitive side effect.
    """
    if mode() not in ("record", "replay-record"):
        return
    evidence = normalize_tool_output_evidence({
        "tool_name": tool_name,
        "result_content": formatted_result,
        "result_digest": hashlib.sha256(formatted_result.encode("utf-8")).hexdigest()
        if isinstance(formatted_result, str) else "",
    })
    if evidence is None:
        logger.warning("llm_cassette: refusing unsafe/bounded tool-output evidence for %r", tool_name)
        return
    _TOOL_EVIDENCE_PENDING.set((*_TOOL_EVIDENCE_PENDING.get(), evidence))


def mode() -> str:
    """Current cassette mode. Unset/empty AQ_LLM_CASSETTE_MODE -> "off" (the
    sacrosanct, silent default — zero behavior change when the operator hasn't
    touched this env var at all). An EXPLICITLY-set but unrecognized mode string is
    a misconfiguration, not "off": raises ReplayConfigError rather than silently
    degrading to a live no-op, which would mask the operator's mistake as a false
    pass."""
    raw = os.environ.get("AQ_LLM_CASSETTE_MODE")
    if raw is None or raw.strip() == "":
        return "off"
    m = raw.strip().lower()
    if m not in _VALID_MODES:
        raise ReplayConfigError(
            f"llm_cassette: AQ_LLM_CASSETTE_MODE={raw!r} is not a valid mode "
            f"(expected one of {_VALID_MODES}) — refusing to silently fall back to 'off'."
        )
    return m


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
    _TOOL_EVIDENCE_PENDING.set(())


# ---------------------------------------------------------------------------
# Orchestration helpers — the thin surface agent_executor._call_llama wires into.
# Both are pure no-ops in mode "off". maybe_record() (recording, a live call) stays
# fail-safe on internal errors, per the module's write-side guardrail. replay_lookup()
# (replay, no network) is fail-CLOSED instead — see its docstring.
# ---------------------------------------------------------------------------

def replay_lookup(
    payload: Dict[str, Any], task_type: Optional[str] = None
) -> Optional[Tuple[str, int]]:
    """Consult the cassette in replay/replay-record modes.

    Returns:
        (content, tokens) on a cassette hit, or on-miss "empty" policy.
        None — proceed with the live call — in mode "off"/"record", on a
              replay-record miss, or on-miss "passthrough". These are the ONLY
              paths that fall through to a live call; every other failure mode
              below is fail-closed (raises).
    Raises:
        ReplayConfigError — AQ_LLM_CASSETTE_MODE is an explicitly-set invalid
              string (from mode()), AQ_LLM_CASSETTE is unset while mode is
              replay/replay-record, or an internal lookup error occurred.
        ReplayDigestMismatch — the request_key() matched a cassette row but the
              full payload digest did not (see Cassette.lookup).
        ReplayMiss — mode "replay", on-miss "error" (the default), and no row
              exists.
    """
    m = mode()  # may raise ReplayConfigError for an explicit-but-invalid mode string
    if m not in ("replay", "replay-record"):
        return None
    cass = get_cassette()
    if cass is None:
        # Replay's whole point is "no network" — a missing cassette path here is a
        # misconfiguration, not a reason to silently run live. Fail closed in BOTH
        # replay and replay-record (replay-record's live-on-miss exemption only
        # covers a clean per-request miss once a cassette path IS configured).
        raise ReplayConfigError(
            f"llm_cassette: mode={m} requires AQ_LLM_CASSETTE to point at a cassette "
            "path — none is set. Refusing to silently proceed live."
        )
    try:
        key = request_key(payload, task_type)
        hit = cass.lookup(key, payload)
    except (ReplayMiss, ReplayConfigError, ReplayDigestMismatch):
        raise
    except Exception as e:
        raise ReplayConfigError(
            f"llm_cassette: internal replay error in mode={m}: {e!r} — failing closed "
            "rather than silently falling back to a live call."
        ) from e

    if hit is not None:
        return hit

    if m == "replay-record":
        return None  # fall through to live; caller records after — explicit exemption

    policy = on_miss()
    if policy == "passthrough":
        return None  # explicit operator opt-in to live fallback on miss
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
        evidence = list(_TOOL_EVIDENCE_PENDING.get())
        _TOOL_EVIDENCE_PENDING.set(())
        merged_meta = dict(meta or {})
        merged_meta["cassette_format_version"] = CASSETTE_FORMAT_VERSION
        if evidence:
            merged_meta["tool_output_evidence"] = evidence
        cass.record(key, payload, content, tokens, merged_meta)
    except Exception:
        logger.exception("llm_cassette: maybe_record internal error — continuing without recording")
