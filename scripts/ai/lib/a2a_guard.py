#!/usr/bin/env python3
"""a2a_guard — message-bus safeguards + audit for agent-to-agent (A2A) traffic.

Even when an external agent's INFERENCE happens in its own runtime (codex CLI,
gemini IDE), its prompts/responses are A2A MESSAGES that should pass a central
safeguard + audit layer. Two functions:

  scan_secrets(text)  -> list[dict]   # canonical secret patterns (pre-commit SSOT)
  audit(record, ...)  -> None         # append a redacted audit line

Highest-value use: scan an OUTBOUND prompt BEFORE it leaves the harness to an
external agent — sending secrets to an external service is a data-exfiltration path.
Import from delegate-to-*/dispatch/aq-collaborate; pure + dependency-free.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# Canonical secret patterns — mirror scripts/.../pre-commit secret guard (SSOT).
_SECRET_PATTERNS = [
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github_pat_classic", re.compile(r"ghp_[A-Za-z0-9]{36}")),
    ("github_pat_fine", re.compile(r"github_pat_[A-Za-z0-9_]{20,}")),
    ("openai_key", re.compile(r"sk-[A-Za-z0-9]{20,}")),
    ("slack_token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private_key", re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY-----")),
    ("assigned_secret", re.compile(
        r"(?i)(?:password|passwd|secret|token|api[_-]?key)\s*[:=]\s*[\"']?[A-Za-z0-9_./+=-]{8,}")),
]

_AUDIT_LOG = os.environ.get(
    "A2A_AUDIT_LOG",
    str(Path(__file__).resolve().parents[3] / ".agent" / "collaboration" / "a2a-audit.log"),
)


def scan_secrets(text: str) -> List[Dict]:
    """Return a list of {kind, match_preview, span} for any secret-like substrings.

    match_preview is redacted (first 4 chars + ***) so the finding itself never
    leaks the secret into logs.
    """
    findings: List[Dict] = []
    if not text:
        return findings
    for kind, pat in _SECRET_PATTERNS:
        for m in pat.finditer(text):
            raw = m.group(0)
            preview = (raw[:4] + "***") if len(raw) > 4 else "***"
            findings.append({"kind": kind, "match_preview": preview, "span": [m.start(), m.end()]})
    return findings


def redact(text: str) -> str:
    """Replace secret-like substrings with a redaction marker (for safe forwarding)."""
    if not text:
        return text
    out = text
    for _kind, pat in _SECRET_PATTERNS:
        out = pat.sub("[REDACTED-SECRET]", out)
    return out


def audit(direction: str, from_agent: str, to_agent: str, summary: str,
          secret_findings: List[Dict] | None = None, task_id: str = "",
          log_path: str | None = None) -> None:
    """Append one redacted audit line for an A2A message. Never blocks the caller."""
    rec = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "direction": direction,          # outbound | inbound
        "from": from_agent,
        "to": to_agent,
        "task_id": task_id,
        "summary": (summary or "")[:200],
        "secret_findings": [f["kind"] for f in (secret_findings or [])],
    }
    try:
        p = Path(log_path or _AUDIT_LOG)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a") as f:
            f.write(json.dumps(rec) + "\n")
    except Exception:
        pass  # audit must never break the delegation


def guard_outbound(text: str, from_agent: str, to_agent: str, task_id: str = "",
                   block: bool = True) -> Dict:
    """Scan + audit an outbound A2A prompt. Returns {ok, findings, text}.

    block=True (default): if secrets found, ok=False and text is redacted — the
    caller should refuse to send raw secrets to an external agent. block=False:
    audit-only (ok=True, text redacted for safe forwarding).
    """
    findings = scan_secrets(text)
    audit("outbound", from_agent, to_agent, text, findings, task_id)
    safe_text = redact(text) if findings else text
    ok = (not findings) or (not block)
    return {"ok": ok, "findings": findings, "text": safe_text}


if __name__ == "__main__":
    import sys
    data = sys.stdin.read()
    res = guard_outbound(data, from_agent="cli", to_agent="external", block=True)
    if res["findings"]:
        print(f"BLOCKED: {len(res['findings'])} secret(s): "
              f"{[f['kind'] for f in res['findings']]}", file=sys.stderr)
        sys.exit(2)
    print("clean")
