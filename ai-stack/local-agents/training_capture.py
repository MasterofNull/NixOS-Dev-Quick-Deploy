#!/usr/bin/env python3
"""P1 — failure capture: turn every local failure into a labeled training sample.

The closed-local-improvement-loop PRD's missing pipe. Today `training_ingest.py` only writes POSITIVE
samples from hybrid-events and merely SUMMARIZES failures — so local's failures (text-as-tool-call,
invalid JSON, truncation) are detected and salvaged but never become training signal. This module is
the capture side: at each failure-detection point (extract_contribution regex-fallback, a failed
tool-call parse, a validate/repair event) the caller records a labeled pair here; `training_ingest`
(P1.2) then ingests these as negative/repair examples for the LoRA loop.

PURE + append-only + failure-tolerant: a capture must NEVER break the caller's hot path. PII is scrubbed
before writing. Default spool is repo-space (.agents/telemetry/) like training_ingest's USER_EVENTS_SPOOL,
so it works even when /var/lib is not writable; override with AQ_TRAINING_SAMPLES.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

_REPO_ROOT = Path(os.getenv("REPO_ROOT", Path(__file__).resolve().parents[2]))
TRAINING_SAMPLES_PATH = Path(
    os.getenv("AQ_TRAINING_SAMPLES", str(_REPO_ROOT / ".agents" / "telemetry" / "training-samples.jsonl"))
)

# Minimal secret scrub (defence-in-depth; the ingest also scrubs). Redacts obvious key/token shapes.
_SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9]{16,}|AIza[A-Za-z0-9_\-]{20,}|ghp_[A-Za-z0-9]{20,}|"
    r"(?i:bearer)\s+[A-Za-z0-9._\-]{16,}|(?i:api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9._\-]{12,})"
)


def _scrub(text: Any, limit: int = 6000) -> str:
    """Redact secret-shaped substrings and bound length. Never raises."""
    try:
        s = text if isinstance(text, str) else json.dumps(text, default=str)
    except Exception:  # noqa: BLE001
        s = str(text)
    s = _SECRET_RE.sub("[REDACTED]", s)
    return s[:limit]


def capture_failure(
    *,
    prompt: Any,
    bad_output: Any,
    failure_class: str,
    tools_available: Optional[list[str]] = None,
    corrected_output: Any = None,
    model_provenance: Optional[dict] = None,
    source: str = "unknown",
    path: Optional[Path] = None,
) -> Optional[Path]:
    """Append a labeled failure sample. Returns the path written, or None on any failure (never raises).

    failure_class: e.g. text_as_tool_call | invalid_tool_json | truncated | parse_failed | validate_failed.
    corrected_output: the correct/repaired output if known (e.g. a remote agent's fix) — enables preference
    pairs; may be None (negative-only sample).
    """
    try:
        target = Path(path) if path is not None else TRAINING_SAMPLES_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "schema_version": "1.0",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": "failure_sample",
            "failure_class": failure_class,
            "source": source,
            "prompt": _scrub(prompt),
            "tools_available": sorted(tools_available) if tools_available else [],
            "bad_output": _scrub(bad_output),
            "corrected_output": _scrub(corrected_output) if corrected_output is not None else None,
            "model_provenance": model_provenance or {},
        }
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return target
    except Exception:  # noqa: BLE001 — capture is best-effort; a failed capture must not break the caller
        return None


def capture_success(
    *,
    prompt: Any,
    good_output: Any,
    source: str = "unknown",
    model_provenance: Optional[dict] = None,
    path: Optional[Path] = None,
) -> Optional[Path]:
    """Append a labeled SUCCESS sample (a good local completion) as a positive training pair.

    This is the reliable positive-sample source: capturing good completions AT the completion point,
    rather than mining hybrid-events.jsonl (which is dominated by RAG/search events — only ~0.03% are
    inference completions, the root cause of the ingest's samples_added:0). Best-effort; never raises.
    """
    try:
        target = Path(path) if path is not None else TRAINING_SAMPLES_PATH
        target.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "schema_version": "1.0",
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "kind": "success_sample",
            "source": source,
            "prompt": _scrub(prompt),
            "good_output": _scrub(good_output),
            "model_provenance": model_provenance or {},
        }
        with open(target, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return target
    except Exception:  # noqa: BLE001
        return None
