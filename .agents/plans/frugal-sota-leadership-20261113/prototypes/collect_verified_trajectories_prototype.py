#!/usr/bin/env python3
"""collect_verified_trajectories_prototype.py — System 2 -> System 1 Distillation Collector (Slice F3).

Incorporates Round 1 Debate fixes from Simurg@claude (claude-20261113-184611-57y8dl):
  1. Applies pattern-based redact_secrets + path normalization across ALL four fields:
     context_packet, rejected_attempts, verified_diff, and review_receipt.
  2. Runs a fail-closed post-redaction gitleaks/high-entropy credential scanner:
     any residual hit QUARANTINES the tuple (refuses to write to trajectories.jsonl
     or stage in upstream-reciprocity/).
"""
from __future__ import annotations

import math
import re
from typing import Any

# Pattern-based redaction (mirrors shared/telemetry_privacy.py:redact_secrets)
_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|authorization)\s*[:=]\s*['\"]?([A-Za-z0-9_\-/.+=]{12,})['\"]?"),
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{30,}"),
    re.compile(r"/run/secrets/[A-Za-z0-9_.\-/]+"),
]

# Post-redaction fail-closed scanner (catches novel high-entropy tokens or unredacted private keys)
_FAIL_CLOSED_RESIDUAL_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-.=]{20,}"),
    re.compile(r"/run/secrets/"),
]

_TOKEN_CANDIDATE_RE = re.compile(r"\b[A-Za-z0-9+/=_\-]{32,}\b")
_HEX_SHA_RE = re.compile(r"^[0-9a-fA-F]{32,64}$")


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    counts: dict[str, int] = {}
    for ch in s:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(s)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


def redact_and_normalize(text: str) -> tuple[str, int]:
    """Redact known secret patterns and normalize /home/<user> paths."""
    hits = 0
    out = text
    for pat in _SECRET_PATTERNS:
        out, n = pat.subn("[REDACTED_SECRET]", out)
        hits += n
    out = re.sub(r"/home/[A-Za-z0-9_.\-]+", "/home/$USER", out)
    return out, hits


def post_redaction_quarantine_scan(text: str) -> list[str]:
    """Fail-closed gitleaks-style residual scanner. Any hit quarantines the tuple."""
    reasons: list[str] = []
    for pat in _FAIL_CLOSED_RESIDUAL_PATTERNS:
        if pat.search(text):
            reasons.append(f"residual_pattern:{pat.pattern}")

    for match in _TOKEN_CANDIDATE_RE.finditer(text):
        tok = match.group(0)
        if _HEX_SHA_RE.match(tok) or "REDACTED" in tok or "_" in tok and tok.islower():
            continue
        # High-entropy mixed-case/symbol token >=32 chars
        has_upper = any(c.isupper() for c in tok)
        has_lower = any(c.islower() for c in tok)
        has_digit = any(c.isdigit() for c in tok)
        if has_upper and has_lower and has_digit and _shannon_entropy(tok) >= 4.3:
            reasons.append("high_entropy_token_candidate")
            break
    return reasons


def sanitize_trajectory_tuple(raw_tuple: dict[str, Any]) -> dict[str, Any]:
    """Scrub and validate (context_packet, rejected_attempts, verified_diff, review_receipt).

    Returns {"status": "accepted" | "quarantined", "quarantine_reasons": [...], "record": {...}}.
    """
    fields = ("context_packet", "rejected_attempts", "verified_diff", "review_receipt")
    scrubbed: dict[str, Any] = dict(raw_tuple)
    total_redactions = 0
    quarantine_reasons: list[str] = []

    for f in fields:
        val = raw_tuple.get(f, "")
        text = "\n".join(str(x) for x in val) if isinstance(val, list) else str(val)
        clean_text, n_hits = redact_and_normalize(text)
        total_redactions += n_hits
        residual = post_redaction_quarantine_scan(clean_text)
        if residual:
            quarantine_reasons.extend(f"{f}:{r}" for r in residual)
        scrubbed[f] = clean_text

    scrubbed["redaction_hits"] = total_redactions
    if quarantine_reasons:
        return {
            "status": "quarantined",
            "quarantine_reasons": quarantine_reasons,
            "record": None,
        }
    return {
        "status": "accepted",
        "quarantine_reasons": [],
        "record": scrubbed,
    }
