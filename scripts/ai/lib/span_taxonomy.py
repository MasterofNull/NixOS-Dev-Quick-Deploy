#!/usr/bin/env python3
"""span_taxonomy — Foundation C, C5 closed span-kind schema + attribute validators.

Design: `.agents/plans/aqos-foundation-c/C5-DESIGN-AND-AUTHORIZATION.md` §3, §6, §8.
C5 is NON-ENFORCEMENT observability: spans OBSERVE already-decided C2/C3b/C4
admission/confinement/egress outcomes, they never gate anything. This module
is the CLOSED taxonomy (§3 table) plus a deny-closed attribute validator: a
span that is malformed in ANY way (unknown kind, missing required attr, a
secret/high-cardinality/raw-path attribute value) is dropped from
projections and flagged — never silently trusted. Pure, offline, NEVER
raises.

A "taxonomy span" is any `trace.py` span whose `name` equals one of the six
closed `SPAN_KINDS` below and whose `attrs` dict is the span's payload. Spans
outside this convention (e.g. the pre-existing `dispatch.local` spans) are
simply not taxonomy candidates — this module never touches or flags them.

Emit-side helper: `emit_taxonomy_span()` is a thin, best-effort wrapper over
`trace.py`'s `span()` context manager (WS5) — no external OpenTelemetry SDK.
Callers are responsible for the `CAPABILITY_SPAN_TRUTH` flag check (this
module performs none itself; it is a pure primitive, reused identically by
shadow-emit call sites and by tests).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional

# ---------------------------------------------------------------------------
# The closed taxonomy (§3)
# ---------------------------------------------------------------------------

SPAN_KINDS: tuple[str, ...] = ("turn", "tool", "lease", "validation", "workspace", "broker")

# Attribute keys that MUST be present (value may be None — presence is what
# is enforced here; enum-constrained fields are additionally value-checked
# via ENUM_VALUES below). `broker.profile_id` is intentionally NOT required
# (§3: "profile_id?").
REQUIRED_ATTRS: dict[str, tuple[str, ...]] = {
    "turn": ("turn_id", "agent", "traceparent"),
    "tool": ("tool", "decision", "reason", "lease_id"),
    "lease": ("lease_id", "parent_lease_id", "revocation_epoch", "op", "decision"),
    "validation": ("verdict", "declared_paths_ok", "grant_digest"),
    "workspace": ("event", "cell_id", "base_oid", "grant_digest"),
    "broker": ("broker", "effect", "decision", "reason", "lease_id"),
}

OPTIONAL_ATTRS: dict[str, tuple[str, ...]] = {
    "broker": ("profile_id",),
}

# Closed enums for specific (kind, attr) pairs. A present-but-out-of-enum
# value is malformed (fails safe, dropped+flagged) — never silently widened.
ENUM_VALUES: dict[tuple[str, str], frozenset[str]] = {
    ("tool", "decision"): frozenset({"admit", "deny", "strip"}),
    ("lease", "op"): frozenset({"issue", "attenuate", "deny", "revoke", "enforce", "degrade"}),
    ("lease", "decision"): frozenset({"admit", "deny"}),
    ("validation", "verdict"): frozenset({"GREEN", "RED"}),
    ("workspace", "event"): frozenset({"snapshot", "rollback", "quarantine"}),
    ("broker", "decision"): frozenset({"allow", "deny", "degrade"}),
}

# `trace.py`'s `span()` context manager unconditionally adds this attr on
# exit (`s.set_attr("duration_s", ...)`) to EVERY span it emits, taxonomy or
# not — an artifact of the shared span primitive, not a taxonomy-specific
# field. It is universally allowed (low-cardinality float, no cardinality/
# secret concern) so a real emitted span is never rejected as "unknown-attrs"
# solely because the primitive it rode in on stamped its own duration.
#
# TAXONOMY_MARKER_* is stamped by `emit_taxonomy_span()` into every span it
# emits and is how `span_projector.py` distinguishes a C5 taxonomy candidate
# from an unrelated pre-existing span (e.g. `dispatch.local`) sharing the
# same event log — the projector never touches/flags a span lacking this
# marker; a MARKED span with a malformed body (bad kind, missing attr) IS
# flagged (§3: never silently trusted).
_UNIVERSAL_OPTIONAL_ATTRS: frozenset[str] = frozenset({"duration_s", "_span_taxonomy"})

TAXONOMY_MARKER_KEY = "_span_taxonomy"
TAXONOMY_MARKER_VALUE = "c5.v1"

ALL_ATTR_NAMES: dict[str, frozenset[str]] = {
    kind: frozenset(REQUIRED_ATTRS.get(kind, ())) | frozenset(OPTIONAL_ATTRS.get(kind, ())) | _UNIVERSAL_OPTIONAL_ATTRS
    for kind in SPAN_KINDS
}

# ---------------------------------------------------------------------------
# Secret-free / low-cardinality enforcement (§3, §6, §8-2)
# ---------------------------------------------------------------------------

MAX_ATTR_STRING_LEN = 128

_FORBIDDEN_KEY_SUBSTRINGS: tuple[str, ...] = (
    "prompt", "payload", "secret", "password", "apikey", "api_key",
    "token", "credential", "raw_path", "file_content", "body", "content",
    "argv", "command_line", "cmdline",
)

_TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}$")


def _looks_like_raw_path(value: str) -> bool:
    """Heuristic: a bytes-on-disk filesystem path, NOT a declared-scope id.

    Declared-scope ids used across this taxonomy (lease_id, grant_digest,
    base_oid, cell_id, turn_id) are opaque hex/uuid/slug tokens with no path
    separators. An attribute value that starts with a path root or contains
    2+ path separators is treated as a raw path and rejected."""
    if value.startswith("/") or value.startswith("~") or value.startswith("\\"):
        return True
    if value.count("/") >= 2:
        return True
    return False


@dataclass(frozen=True)
class ValidationOutcome:
    ok: bool
    reason: Optional[str] = None
    kind: Optional[str] = None


def _attr_violation(key: str, value: Any) -> Optional[str]:
    """Return a violation reason string, or None if `value` is clean."""
    lk = key.lower()
    for bad in _FORBIDDEN_KEY_SUBSTRINGS:
        if bad in lk:
            return f"forbidden-attr-key:{key}"
    if value is None or isinstance(value, bool) or isinstance(value, (int, float)):
        return None
    if isinstance(value, str):
        if "\n" in value or "\r" in value:
            return f"attr-contains-newline:{key}"
        if len(value) > MAX_ATTR_STRING_LEN:
            return f"attr-too-long:{key}"
        # traceparent is the one attribute whose value legitimately contains
        # hyphens in a fixed W3C shape; exempt it from the raw-path heuristic
        # (it never contains "/").
        if key != "traceparent" and _looks_like_raw_path(value):
            return f"attr-looks-like-raw-path:{key}"
        return None
    return f"attr-unsupported-type:{key}:{type(value).__name__}"


def validate_span(record: dict) -> ValidationOutcome:
    """Validate one candidate taxonomy span record.

    `record` shape: `{"kind": str, "attrs": dict, ...}` (extra keys such as
    `agent`/`ts`/`status` are ignored by this validator — it only enforces
    the closed-taxonomy attribute contract). NEVER raises: any internal
    error is itself reported as a (False, "validator-internal-error:...")
    outcome rather than propagating, matching every other fail-closed
    validator in this harness (e.g. `capability_lease_gate.enforce`)."""
    try:
        kind = record.get("kind") if isinstance(record, dict) else None
        if not isinstance(kind, str) or kind not in SPAN_KINDS:
            return ValidationOutcome(False, "unknown-span-kind", kind if isinstance(kind, str) else None)

        attrs = record.get("attrs")
        if not isinstance(attrs, dict):
            return ValidationOutcome(False, "attrs-not-dict", kind)

        required = REQUIRED_ATTRS.get(kind, ())
        missing = sorted(a for a in required if a not in attrs)
        if missing:
            return ValidationOutcome(False, f"missing-required-attrs:{','.join(missing)}", kind)

        allowed_names = ALL_ATTR_NAMES.get(kind, frozenset())
        unknown = sorted(k for k in attrs if k not in allowed_names)
        if unknown:
            return ValidationOutcome(False, f"unknown-attrs:{','.join(unknown)}", kind)

        for key, value in attrs.items():
            violation = _attr_violation(key, value)
            if violation:
                return ValidationOutcome(False, violation, kind)

        for (ekind, field), allowed in ENUM_VALUES.items():
            if ekind != kind:
                continue
            val = attrs.get(field)
            if val is not None and val not in allowed:
                return ValidationOutcome(False, f"invalid-enum-value:{field}={val}", kind)

        if kind == "turn":
            tp = attrs.get("traceparent")
            if not isinstance(tp, str) or not _TRACEPARENT_RE.match(tp):
                return ValidationOutcome(False, "invalid-traceparent", kind)

        return ValidationOutcome(True, None, kind)
    except Exception as exc:  # noqa: BLE001 — deny-closed, never raise
        return ValidationOutcome(False, f"validator-internal-error:{type(exc).__name__}", None)


# ---------------------------------------------------------------------------
# W3C Trace Context helpers (§3, §7 — traceparent links + A2A hop crossing)
# ---------------------------------------------------------------------------


def w3c_traceparent(trace_id: str, span_id: str, *, sampled: bool = True) -> str:
    """Build a W3C `traceparent` header value: `00-{trace_id:32hex}-{span_id:16hex}-{flags}`.

    `trace.py` already generates 32-hex trace ids and 16-hex span ids
    (`_gen_id(32)` / `_gen_id(16)`), so this is a pure formatting helper —
    no new id scheme."""
    flags = "01" if sampled else "00"
    return f"00-{trace_id}-{span_id}-{flags}"


def parse_traceparent(value: str) -> Optional[tuple[str, str]]:
    """Return `(trace_id, span_id)` if `value` is a well-formed W3C
    traceparent, else None. Never raises."""
    try:
        if not isinstance(value, str) or not _TRACEPARENT_RE.match(value):
            return None
        _version, trace_id, span_id, _flags = value.split("-")
        return trace_id, span_id
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Flag + emit primitive (§5) — callers own the flag check; this function
# performs none itself so it stays a pure, independently-testable primitive.
# ---------------------------------------------------------------------------

FLAG_ENV = "CAPABILITY_SPAN_TRUTH"


def span_truth_enabled(env: Optional[dict] = None) -> bool:
    """True iff the C5 observability flag is explicitly ON. Default OFF —
    an absent/unrecognized value is OFF, never ON (deny-closed on the flag,
    matching every other flag in this harness)."""
    source = env if env is not None else os.environ
    return source.get(FLAG_ENV, "0") == "1"


def emit_taxonomy_span(kind: str, *, agent: str, attrs: dict) -> None:
    """Best-effort emission of one closed-taxonomy span via `trace.py`'s
    `span()` (WS5 event bus — no external OTel SDK). The span `name` IS the
    taxonomy `kind` by convention; `attrs` carries the kind's required
    fields. This is a ZERO-DURATION span (the decision it observes has
    already been made synchronously by the caller) — it exists purely to
    put the decision on the trace/event log for projection.

    NEVER raises and NEVER validates `kind`/`attrs` itself (callers SHOULD
    construct well-formed attrs; `validate_span()` is the deny-closed
    backstop applied at PROJECTION time — a malformed span that reaches the
    log is dropped+flagged there, never trusted, matching §3's "never
    silently trusted" contract). Callers own the `CAPABILITY_SPAN_TRUTH`
    flag check — this primitive performs none, so it stays independently
    testable without env-var coupling."""
    try:
        import trace as _trace  # local import: scripts/ai/lib is on sys.path
        marked = dict(attrs)
        marked[TAXONOMY_MARKER_KEY] = TAXONOMY_MARKER_VALUE
        with _trace.span(kind, agent=agent, attrs=marked):
            pass
    except Exception:  # noqa: BLE001 — telemetry must never break a caller
        pass


if __name__ == "__main__":
    import json
    import sys

    print(json.dumps({
        "span_kinds": list(SPAN_KINDS),
        "required_attrs": {k: list(v) for k, v in REQUIRED_ATTRS.items()},
    }, indent=2))
    sys.exit(0)
