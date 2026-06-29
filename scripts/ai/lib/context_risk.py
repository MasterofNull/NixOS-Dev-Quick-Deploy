#!/usr/bin/env python3
"""Shared context-risk detection and artifact compaction helpers."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / ".agents" / "context-artifacts"
DEFAULT_MIN_CHARS = int(os.getenv("SWB_CONTEXT_OUTPUT_GC_MIN_CHARS", "2400"))
DEFAULT_SUMMARY_CHARS = int(os.getenv("SWB_CONTEXT_OUTPUT_GC_SUMMARY_CHARS", "900"))
_HIGH_PAYLOAD_HINT_RE = re.compile(
    r"\b(log|traceback|html|snapshot|playwright|journalctl|pytest|aq-qa|find|rg|grep|tree|diff)\b",
    re.IGNORECASE,
)


def _artifact_dir() -> Path:
    raw = os.getenv("SWB_CONTEXT_ARTIFACT_DIR", "").strip()
    if raw:
        return Path(os.path.expandvars(os.path.expanduser(raw)))
    return DEFAULT_ARTIFACT_DIR


def _safe_label(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in value.lower())
    cleaned = "-".join(part for part in cleaned.split("-") if part)
    return (cleaned or "context")[:64]


def _preview(text: str, limit: int) -> str:
    compact = " ".join(str(text or "").replace("\x00", "").split())
    if len(compact) <= limit:
        return compact
    return compact[: max(0, limit - 3)].rstrip() + "..."


def classify_context_risk(
    text: str,
    *,
    source: str = "",
    min_chars: int = DEFAULT_MIN_CHARS,
) -> dict[str, Any]:
    """Classify whether a payload should be stored as an artifact before LLM injection."""
    raw = str(text or "")
    reasons: list[str] = []
    line_count = raw.count("\n") + (1 if raw else 0)
    if len(raw) >= min_chars:
        reasons.append("large_payload")
    if line_count >= 80:
        reasons.append("many_lines")
    if _HIGH_PAYLOAD_HINT_RE.search(source or "") and len(raw) >= max(800, min_chars // 2):
        reasons.append("source_high_payload")
    if raw.count("Traceback (most recent call last)") >= 2:
        reasons.append("repeated_traceback")
    if raw.count("<html") or raw.count("<div"):
        if len(raw) >= max(800, min_chars // 2):
            reasons.append("html_snapshot")
    return {
        "context_risk": bool(reasons),
        "reasons": reasons,
        "chars": len(raw),
        "lines": line_count,
        "min_chars": min_chars,
        "route": "switchboard-artifact+aq-context-manage" if reasons else "inline",
    }


def compact_context_if_needed(
    text: str,
    *,
    source: str,
    label: str,
    kind: str = "text",
    tool_call_id: str | None = None,
    min_chars: int = DEFAULT_MIN_CHARS,
    summary_chars: int = DEFAULT_SUMMARY_CHARS,
    artifact_dir: Path | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return original text or a compact artifact envelope plus telemetry metadata."""
    raw = str(text or "")
    risk = classify_context_risk(raw, source=source, min_chars=min_chars)
    if not risk["context_risk"]:
        return raw, risk

    encoded = raw.encode("utf-8", errors="replace")
    digest = hashlib.sha256(encoded).hexdigest()
    target_dir = artifact_dir or _artifact_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = target_dir / f"{int(time.time())}-{_safe_label(label)}-{digest[:12]}.json"
    artifact_payload = {
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kind": kind,
        "label": label,
        "source": source,
        "tool_call_id": tool_call_id,
        "sha256": digest,
        "raw_chars": len(raw),
        "content": raw,
    }
    artifact_path.write_text(json.dumps(artifact_payload, ensure_ascii=True, indent=2), encoding="utf-8")

    envelope = {
        "status": "compacted",
        "context_risk": True,
        "context_route": risk["route"],
        "risk_reasons": risk["reasons"],
        "kind": kind,
        "source": source,
        "label": label,
        "artifact_path": str(artifact_path),
        "sha256": digest,
        "raw_chars": len(raw),
        "raw_output_compacted": True,
        "summary_chars": summary_chars,
        "summary": _preview(raw, summary_chars),
        "resume_command": f'aq-context-manage summary --task "{_safe_label(label)}" --json',
        "usage": "Pass artifact_path and summary forward; do not paste the raw payload into model context.",
    }
    return json.dumps(envelope, ensure_ascii=True, sort_keys=True), {**risk, **envelope}


def context_risk_empty_stats() -> dict[str, Any]:
    return {
        "context_risk_routes": 0,
        "context_risk_chars": 0,
        "context_risk_reasons": {},
    }
