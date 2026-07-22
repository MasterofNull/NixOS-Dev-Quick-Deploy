#!/usr/bin/env python3
"""aq-evidence-collector.py — standalone unwrapped evidence recorder (VF-7).

Track V (Verified Factory) slice VF-7: a dedicated, unwrapped, raw-binary
evidence collector. Test-run evidence (command stdout/stderr, or a piped raw
stream) can be distorted or truncated when it passes through tool wrappers
(e.g. lean-ctx stdout compression). This script never routes through any such
wrapper: it either subprocess.run()s the target command itself (capturing raw
bytes directly from the OS pipes) or reads sys.stdin.buffer directly, so the
bytes it hashes are exactly the bytes the process emitted.

Security invariant (deliberate, read before changing): the SHA-256 digest is
computed over the RAW, pre-redaction bytes — (timestamp + payload_bytes +
caller_agent_id) — but only the REDACTED text is ever written to disk. The
raw bytes exist solely in this process's memory for the instant it takes to
hash and redact them; they are never logged, never written, and never
returned to the caller. This satisfies both "digest of payload_bytes" and
"redact BEFORE writing" without ever persisting a secret, even transiently.

Shared-ledger note: `.agents/events/a2a-events.jsonl` is also the event log
for `aq-event` (resume.update / pulse.append projections, see
scripts/ai/lib/event_log.py + resume_projector.py). Every record this script
appends is a schema-compatible `contracts.events.Envelope` (same top-level
shape, extra="forbid"-safe) so existing readers never choke on it, but its
`type` is the dotted namespace "vf7.evidence.v1" — distinct from
"resume.update"/"pulse.append" — and its payload carries a `"kind":
"vf7.evidence.v1"` discriminator, so existing consumers can trivially filter
these records out (or in) without any schema surprise.

Usage:
    # Capture a command's own raw stdout+stderr (recommended: fully unwrapped)
    aq-evidence-collector.py record --caller-agent-id NAME --command "pytest -q" \\
        [--subject "phase0"] [--ledger PATH]

    # Or pipe an already-captured raw stream in directly
    some-raw-producer | aq-evidence-collector.py record --caller-agent-id NAME --stdin

Exit codes: 0 on success, 1 on any failure (never partially writes a record).
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCHEMA_VERSION = 1
RECORD_KIND = "vf7.evidence.v1"
EVENT_TYPE = "vf7.evidence.v1"

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LEDGER = _REPO_ROOT / ".agents" / "events" / "a2a-events.jsonl"

# ── redaction ────────────────────────────────────────────────────────────────
# Deliberately conservative (over-redact rather than leak). Order matters:
# structured secrets (PEM blocks, bearer headers, known token prefixes) are
# stripped before the generic KEY/TOKEN/SECRET=value sweep so a token embedded
# inside e.g. an Authorization header does not also leave a dangling partial
# match for the generic pass to mis-handle.

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-_.=]+")
_BASIC_AUTH_RE = re.compile(r"(?i)\bBasic\s+[A-Za-z0-9+/=]{8,}")
# Known-prefix OAuth/API tokens (GitHub, Google, OpenAI/Anthropic-style, Slack).
_KNOWN_TOKEN_RE = re.compile(
    r"\b(?:gh[oparsu]_[A-Za-z0-9]{20,}|ya29\.[A-Za-z0-9_\-.]+|"
    r"sk-[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9\-]{10,}|"
    r"eyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+)\b"
)
_SSH_KEY_ONELINE_RE = re.compile(
    r"\b(?:ssh-(?:rsa|ed25519|dss)|ecdsa-sha2-[a-z0-9]+)\s+[A-Za-z0-9+/=]{20,}"
)
# Generic NAME=value / export NAME=value where NAME looks secret-ish. Anchored
# on "no word-char immediately before" (not line-start) so it also catches
# KEY=value sitting mid-line in captured stdout (e.g. "ok API_KEY=xyz done"),
# not just the env-file/`export FOO=bar` shape.
_SECRET_VAR_RE = re.compile(
    r"(?i)(?P<prefix>(?<![A-Za-z0-9_])(?:export\s+)?)(?P<name>[A-Z_][A-Z0-9_]*"
    r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PASS|CREDENTIAL|CREDENTIALS|APIKEY))"
    r"(?P<eq>\s*=\s*)(?P<value>\S+)"
)


def redact(text: str) -> str:
    """Strip environment secrets, bearer/basic auth, and private keys.

    Applied to a str (the collector decodes captured bytes as UTF-8 with
    errors="replace" before this call — redaction never needs to reason about
    raw binary).
    """
    text = _PRIVATE_KEY_RE.sub("[REDACTED_PRIVATE_KEY]", text)
    text = _SSH_KEY_ONELINE_RE.sub("[REDACTED_SSH_PUBLIC_OR_KEY_MATERIAL]", text)
    text = _BEARER_RE.sub("Bearer [REDACTED_TOKEN]", text)
    text = _BASIC_AUTH_RE.sub("Basic [REDACTED_TOKEN]", text)
    text = _KNOWN_TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    text = _SECRET_VAR_RE.sub(
        lambda m: f"{m.group('prefix')}{m.group('name')}{m.group('eq')}[REDACTED]", text
    )
    return text


# ── digest ───────────────────────────────────────────────────────────────────

def compute_digest(timestamp: str, payload_bytes: bytes, caller_agent_id: str) -> str:
    """Immutable SHA-256 digest of (timestamp + payload_bytes + caller_agent_id).

    Pure function: identical inputs always yield the identical digest, and it
    is the caller's responsibility to never call this twice with the same
    timestamp for genuinely different evidence (each record mints its own
    timestamp, so honest re-invocations always produce a fresh one).
    """
    h = hashlib.sha256()
    h.update(timestamp.encode("utf-8"))
    h.update(payload_bytes)
    h.update(caller_agent_id.encode("utf-8"))
    return h.hexdigest()


# ── record construction ─────────────────────────────────────────────────────

def build_record(
    *,
    caller_agent_id: str,
    payload_bytes: bytes,
    stream: str,
    subject: Optional[str] = None,
    command: Optional[str] = None,
    exit_code: Optional[int] = None,
) -> dict[str, Any]:
    """Build one Envelope-shaped evidence record. payload_bytes is the RAW
    pre-redaction evidence; only its redacted decode is persisted in the
    returned record's payload.evidence_text — payload_bytes itself is never
    stored, only hashed.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    digest = compute_digest(timestamp, payload_bytes, caller_agent_id)
    decoded = payload_bytes.decode("utf-8", errors="replace")
    evidence_text = redact(decoded)

    payload: dict[str, Any] = {
        "kind": RECORD_KIND,
        "digest": digest,
        "digest_algorithm": "sha256",
        "digest_over": ["timestamp", "payload_bytes", "caller_agent_id"],
        "timestamp": timestamp,
        "caller_agent_id": caller_agent_id,
        "stream": stream,
        "byte_length": len(payload_bytes),
        "redacted": evidence_text != decoded,
        "evidence_text": evidence_text,
    }
    if command is not None:
        # The invoked command line itself can carry a secret (e.g. a
        # --token=... flag) — redact it the same as the captured evidence
        # before it is ever persisted.
        payload["command"] = redact(command)
    if exit_code is not None:
        payload["exit_code"] = exit_code

    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": uuid.uuid4().hex,
        "ts": time.time(),
        "agent": caller_agent_id,
        "type": EVENT_TYPE,
        "subject": subject,
        "payload": payload,
        "sig": None,
        "trace_id": None,
        "span_id": None,
        "parent_span_id": None,
    }


def verify_record_digest(record: dict[str, Any], payload_bytes: bytes) -> bool:
    """Recompute the digest from a record's own timestamp/caller_agent_id plus
    caller-supplied raw bytes, and confirm it matches what was stored. Used to
    prove digest immutability: this must hold for any record, any time, given
    the original raw bytes."""
    p = record["payload"]
    expected = compute_digest(p["timestamp"], payload_bytes, p["caller_agent_id"])
    return expected == p["digest"]


# ── append-only ledger write (fcntl.flock, never truncate/modify) ──────────

def append_record(record: dict[str, Any], ledger_path: Path = DEFAULT_LEDGER) -> None:
    """Append one record as a single JSON line. O_APPEND + an exclusive
    fcntl.flock around the write makes this collector's own writes
    transactional (serialized, all-or-nothing) with respect to any other
    process that also takes the lock. Never opens with O_TRUNC; never seeks;
    never rewrites a prior byte.

    Newline placement is LEADING, not trailing — this matches
    scripts/ai/lib/event_log.py's own convention for this shared ledger. If a
    crashed writer (ours or aq-event's) left a torn line with no terminating
    newline, our leading "\\n" starts us on a fresh line instead of gluing our
    JSON onto — and thereby corrupting both — that partial line. Using the
    opposite (trailing-only) convention here would silently corrupt whichever
    of our record or aq-event's record happens to land second, since
    aq-event's writer does not terminate its own lines either.
    """
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(record, sort_keys=True, separators=(",", ":"))
    line = "\n" + body
    data = line.encode("utf-8")
    fd = os.open(str(ledger_path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            os.write(fd, data)
            os.fsync(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


# ── raw capture ──────────────────────────────────────────────────────────────

def capture_command(command: str) -> tuple[bytes, int]:
    """Run `command` through the shell and return its raw combined
    stdout+stderr bytes exactly as the OS delivered them (no wrapper, no line
    stripping, no compression) plus its exit code."""
    proc = subprocess.run(
        command,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.stdout, proc.returncode


def capture_stdin() -> bytes:
    """Read raw bytes directly from stdin (piped-in evidence)."""
    return sys.stdin.buffer.read()


# ── CLI ──────────────────────────────────────────────────────────────────────

def _cmd_record(args: argparse.Namespace) -> int:
    exit_code: Optional[int] = None
    command: Optional[str] = None
    if args.command:
        command = args.command
        raw, exit_code = capture_command(args.command)
        stream = "combined"
    elif args.stdin:
        raw = capture_stdin()
        stream = "stdin"
    else:
        print("aq-evidence-collector: one of --command or --stdin is required", file=sys.stderr)
        return 1

    record = build_record(
        caller_agent_id=args.caller_agent_id,
        payload_bytes=raw,
        stream=stream,
        subject=args.subject,
        command=command,
        exit_code=exit_code,
    )
    ledger_path = Path(args.ledger) if args.ledger else DEFAULT_LEDGER
    append_record(record, ledger_path)
    print(record["event_id"])
    if exit_code is not None:
        return 0  # collector's own success is independent of the captured command's exit code
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="aq-evidence-collector.py")
    sub = parser.add_subparsers(dest="cmd", required=True)

    rec = sub.add_parser("record", help="capture and append one unwrapped evidence record")
    rec.add_argument("--caller-agent-id", required=True)
    rec.add_argument("--subject", default=None)
    rec.add_argument("--ledger", default=None, help="override ledger path (default: .agents/events/a2a-events.jsonl)")
    src = rec.add_mutually_exclusive_group(required=False)
    src.add_argument("--command", default=None, help="shell command to run and capture raw stdout+stderr from")
    src.add_argument("--stdin", action="store_true", help="read raw evidence bytes from stdin")
    rec.set_defaults(func=_cmd_record)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
