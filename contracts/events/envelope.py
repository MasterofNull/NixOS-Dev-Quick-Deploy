"""A2A event envelope — the single message type on the harness event log.

Design contracts:
  - event_id is the idempotency key: emitting the same id twice is a no-op at
    read time (the projector dedups). Default is content+time derived so honest
    re-emits collapse but distinct events never collide.
  - ts is epoch seconds (float) — sortable, timezone-free, cheap.
  - type is a dotted namespace: "resume.update", "pulse.append", "delegation.*".
  - sig is optional HMAC-SHA256 over the canonical body; unsigned envelopes are
    accepted in v1 (signing ENFORCEMENT is a later slice), but a present sig
    MUST verify or the event is rejected by the reader.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = 1


def new_event_id() -> str:
    """A unique event id (uuid4 hex). Callers may pass a deterministic id instead
    to get idempotent collapse of honest retries."""
    return uuid.uuid4().hex


class Envelope(BaseModel):
    """One event on the log. extra=forbid so typos in producers fail loudly."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    event_id: str = Field(default_factory=new_event_id)
    ts: float = Field(default_factory=lambda: time.time())
    agent: str
    type: str
    subject: Optional[str] = None          # what the event is about (file/scope/round)
    payload: dict[str, Any] = Field(default_factory=dict)
    sig: Optional[str] = None              # HMAC-SHA256 hex over canonical body
    # Distributed tracing (WS5): one trace_id per operator intent flows CLI ->
    # bus -> dispatch -> model -> tools -> commit. span_id/parent_span_id form
    # the tree. All optional so non-traced events are unaffected.
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    # ── signing ──────────────────────────────────────────────────────────────
    def _canonical_body(self) -> bytes:
        """Deterministic bytes for signing/verifying (excludes sig itself)."""
        body = {
            "schema_version": self.schema_version,
            "event_id": self.event_id,
            "ts": self.ts,
            "agent": self.agent,
            "type": self.type,
            "subject": self.subject,
            "payload": self.payload,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
        }
        return json.dumps(body, sort_keys=True, separators=(",", ":")).encode()

    def signed(self, key: Optional[bytes] = None) -> "Envelope":
        """Return a copy with sig set. No-op (unsigned) when no key is available."""
        k = key if key is not None else _signing_key()
        if not k:
            return self
        mac = hmac.new(k, self._canonical_body(), hashlib.sha256).hexdigest()
        return self.model_copy(update={"sig": mac})

    def verify(self, key: Optional[bytes] = None) -> bool:
        """True if unsigned (v1 accepts), or signed and the HMAC matches."""
        if self.sig is None:
            return True
        k = key if key is not None else _signing_key()
        if not k:
            # A sig is present but we have no key to check it — reject: an event
            # claiming to be signed must be verifiable.
            return False
        expect = hmac.new(k, self._canonical_body(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expect, self.sig)


def _signing_key() -> Optional[bytes]:
    """HMAC key from env/SOPS runtime path, or None (unsigned mode).

    Never hardcoded. Source order: A2A_EVENT_SIGNING_KEY env, then the
    SOPS-provisioned runtime file if present. Absent => unsigned v1 mode.
    """
    env = os.environ.get("A2A_EVENT_SIGNING_KEY", "").strip()
    if env:
        return env.encode()
    for p in ("/run/secrets/a2a_event_signing_key",):
        try:
            with open(p, "rb") as fh:
                data = fh.read().strip()
                if data:
                    return data
        except OSError:
            continue
    return None
