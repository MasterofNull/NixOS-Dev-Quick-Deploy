"""ApprovalRequest primitive — Approval Control Plane P0 (crypto-free for the
human; no enforcement service, no WebAuthn, no owner keys).

Implements the `aq.approval-request.v1` closed record schema, its privacy
boundary, its bounded-action (registered-runbook) constraint, its canonical
hash, and its `pending -> approved -> executed` state machine, per
`.agents/plans/approval-control-plane/ACP-P0-DESIGN-20260816.md`
(authoritative — including the review-fold findings #7-#9 folded into that
packet, cited by number below). This module performs NO enforcement and
calls NO service: `validate()`/`compute_hash()` only *report*; `transition()`
builds a new record + audit event but writes nothing durable; the audited
*executor* that actually runs a runbook lives in the sibling
`approval_executor.py` and is the only thing in this pair with side effects
(and even those are P0 in-memory stubs — see that module's docstring).

Why a record schema is P0's whole job: later slices (P1 WebAuthn signing
service) close the "what-you-see-is-not-what-you-sign" hole by having the
signer fetch the canonical request itself by id and derive the challenge
from it. That only works if the record is closed/bounded, canonically
hashable, and split into a plain-language layer (`summary`, Layer 1) the
human reads and a technical layer (`technical_trail`, Layer 3) they never
need to. This module is exactly that substrate.

Three layers, one hard privacy boundary (design invariant 2 — "the
load-bearing one"): `summary` (Layer 1, plain language, the ONLY thing a
surface shows by default) MUST NEVER contain a sha256 hex digest, a
`/run/secrets` reference, a filesystem path, a key id, a socket path, or the
literal string "sha256". `technical_trail` (Layer 3) is where hashes/paths/
keys live, and it is never surfaced by default. `summary` is also NOT free
text (review finding #7): each registered runbook ships a summary template
(title/what/why) rendered deterministically from its typed `params`, plus an
`impact` DERIVED from the runbook's own risk class — never asserted by the
caller. `validate()` recomputes this projection and rejects any record whose
`summary` diverges from it, so the words a human reads and the action the
executor runs cannot drift apart.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional

# --------------------------------------------------------------------------
# Constants — closed `aq.approval-request.v1` schema
# --------------------------------------------------------------------------

SCHEMA_ID = "aq.approval-request.v1"

TOP_LEVEL_KEYS = frozenset(
    {
        "schema",
        "request_id",
        "created_at",
        "created_by",
        "status",
        "summary",
        "required_authority",
        "action_manifest",
        "technical_trail",
        "binding",
    }
)
SUMMARY_KEYS = frozenset({"title", "what", "why", "impact", "reversible"})
ACTION_MANIFEST_KEYS = frozenset({"runbook", "params", "declared_effects"})
TECHNICAL_TRAIL_KEYS = frozenset({"design_sha256", "target_files", "grant_subject"})
BINDING_KEYS = frozenset({"canonical_hash", "requester_sig"})

MAX_TITLE_LEN = 80
IMPACT_LEVELS = ("low", "medium", "high")

# P0 only DEFINES this enum (design line 48: "P1 enforces"); a single member
# for now — the executor contract does not branch on it yet.
REQUIRED_AUTHORITY_VALUES = ("owner-webauthn",)

# --------------------------------------------------------------------------
# State machine (design invariant 5) — pending -> approved -> executed
# (happy path); pending -> denied (terminal); approved -> failed (terminal,
# executor error); pending -> expired (terminal, TTL). No other transitions.
# --------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_EXECUTED = "executed"
STATUS_DENIED = "denied"
STATUS_FAILED = "failed"
STATUS_EXPIRED = "expired"

STATUSES = (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_EXECUTED,
    STATUS_DENIED,
    STATUS_FAILED,
    STATUS_EXPIRED,
)

ALLOWED_TRANSITIONS: dict[str, frozenset] = {
    STATUS_PENDING: frozenset({STATUS_APPROVED, STATUS_DENIED, STATUS_EXPIRED}),
    STATUS_APPROVED: frozenset({STATUS_EXECUTED, STATUS_FAILED}),
    STATUS_EXECUTED: frozenset(),
    STATUS_DENIED: frozenset(),
    STATUS_FAILED: frozenset(),
    STATUS_EXPIRED: frozenset(),
}

# --------------------------------------------------------------------------
# Typed, safe-to-log reason vocabulary — `validate()` never raises; every
# denial is one of these (mirrors `revocation_epoch.DENY_*` /
# `capability_lease.AUTH_DENY_*`).
# --------------------------------------------------------------------------

VERIFY_OK = "ok"

REJECT_NOT_A_MAPPING = "not-a-mapping"
REJECT_TOP_LEVEL_SCHEMA = "top-level-schema-mismatch"
REJECT_SCHEMA_ID = "schema-id-mismatch"
REJECT_ENVELOPE_FIELD = "envelope-field-invalid"
REJECT_UNKNOWN_STATUS = "unknown-status"
REJECT_SUMMARY_SCHEMA = "summary-schema-mismatch"
REJECT_REQUIRED_AUTHORITY = "required-authority-invalid"
REJECT_REQUIRED_AUTHORITY_MISMATCH = "required-authority-mismatch"
REJECT_ACTION_MANIFEST_SCHEMA = "action-manifest-schema-mismatch"
REJECT_UNKNOWN_RUNBOOK = "unknown-runbook"
REJECT_PARAM_TYPE = "param-type-invalid"
REJECT_PARAM_KEYS = "param-keys-mismatch"
REJECT_PARAM_PATTERN = "param-pattern-invalid"
REJECT_DECLARED_EFFECTS_MISMATCH = "declared-effects-mismatch"
REJECT_SUMMARY_MISMATCH = "summary-not-rendered-from-template"
REJECT_TECHNICAL_TRAIL_SCHEMA = "technical-trail-schema-mismatch"
REJECT_BINDING_SCHEMA = "binding-schema-mismatch"
REJECT_INTERNAL = "internal-error"

# Privacy-boundary denial reasons (design invariant 2). Each corresponds to
# one banned pattern in `summary`.
LEAK_HEX64 = "privacy-leak-hex64"
LEAK_RUN_SECRETS = "privacy-leak-run-secrets"
LEAK_FILESYSTEM_PATH = "privacy-leak-filesystem-path"
LEAK_KEY_ID = "privacy-leak-key-id"
LEAK_SOCKET_PATH = "privacy-leak-socket-path"
LEAK_SHA256_LITERAL = "privacy-leak-sha256-literal"

REJECT_ILLEGAL_TRANSITION = "illegal-transition"
REJECT_INVALID_RECORD = "invalid-record"


class ApprovalValidationError(Exception):
    """Raised by the *builder* (`create_request`) on a bad request — never
    raised by `validate()` itself, which is a total, never-raising verdict
    function (mirrors `capability_lease.verify` / `revocation_epoch.verify_bump`)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class ApprovalStateError(Exception):
    """Raised by `transition()` on an illegal transition or an already-invalid
    input record. Fail-closed: no new record and no event are produced."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


@dataclass(frozen=True)
class ValidationVerdict:
    """Typed, report-only outcome of `validate()` — never raises, never acts.
    `ok=True` iff `reason == VERIFY_OK`; every other `reason` is one of the
    `REJECT_*`/`LEAK_*` constants above and is safe to log."""

    ok: bool
    reason: str
    detail: str = ""


# --------------------------------------------------------------------------
# Runbook registry (design invariant 3 — bounded action). Approving a
# request can never execute an arbitrary command: only a named, pre-
# reviewed runbook with typed params. `required_authority`, `risk_class`
# (-> `summary.impact`), `reversible`, and `declared_effects` are all
# REGISTRY-OWNED, never caller-supplied, so nothing free-form can smuggle
# past `action_manifest` (closes the PRD-R2 "downgrade/arbitrary-action"
# hole cited in the design packet).
# --------------------------------------------------------------------------

SERVICE_NAME_PATTERN = r"^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$"

# Tighter identifier allowlist for the ACP-P3 runbooks below (`rotate-key`,
# `epoch-revoke`, `emit-grant`, `activate-foundation-c-slice`): same
# lowercase-alnum-hyphen char class as `SERVICE_NAME_PATTERN`, but bounded to
# 3-32 chars (not 3-64). Deliberately shorter: those runbooks' title
# templates carry more fixed prose than `activate-signer-service`'s, so a
# 64-char param at `render_summary()` time could push `summary.title` past
# `MAX_TITLE_LEN` (80) and make an otherwise-legitimate request fail
# `validate()`. 32 chars leaves headroom for every template below.
IDENTIFIER_PATTERN = r"^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$"


@dataclass(frozen=True)
class RunbookSpec:
    name: str
    required_authority: str
    risk_class: str  # low | medium | high -> summary.impact (never caller-set)
    reversible: bool
    declared_effects: tuple
    param_schema: dict  # param_name -> {"type": "str"|"int"|"bool", "pattern": Optional[str]}
    title_template: str
    what_template: str
    why_template: str
    effect: Callable[..., dict]


def _effect_activate_signer_service(*, service: str) -> dict[str, Any]:
    """P0 stub effect — NOT a real activation, opens no socket, touches no
    Nix/systemd surface. Returns a deterministic result dict the executor
    records as an audited event payload. A later slice replaces this
    registry entry's `effect` with a call into the real audited AQ action
    path; the executor contract in `approval_executor.py` does not change."""
    return {"runbook": "activate-signer-service", "service": service, "result": "activated"}


def _effect_restart_service(*, service: str) -> dict[str, Any]:
    """P0 stub effect — see `_effect_activate_signer_service` docstring."""
    return {"runbook": "restart-service", "service": service, "result": "restarted"}


def _effect_rotate_key(*, subject: str) -> dict[str, Any]:
    """P0-style single-shot stub effect for `rotate-key` — NOT a real key
    rotation (no key material, no SOPS, no allowlist write). See
    `_effect_activate_signer_service` docstring for why this exists
    alongside the P3 multi-step engine's own stub atoms: this is only the
    single-call path `approval_executor.py` still uses; the real per-step
    idempotent execution for this runbook is
    `approval_runbook_engine.STEP_REGISTRY["rotate-key"]`."""
    return {"runbook": "rotate-key", "subject": subject, "result": "rotated"}


def _effect_epoch_revoke(*, epoch_scope: str) -> dict[str, Any]:
    """P0-style single-shot stub effect for `epoch-revoke` — see
    `_effect_rotate_key` docstring."""
    return {"runbook": "epoch-revoke", "epoch_scope": epoch_scope, "result": "revoked"}


def _effect_emit_grant(*, grant_subject: str) -> dict[str, Any]:
    """P0-style single-shot stub effect for `emit-grant` — see
    `_effect_rotate_key` docstring."""
    return {"runbook": "emit-grant", "grant_subject": grant_subject, "result": "granted"}


def _effect_activate_foundation_c_slice(*, slice: str) -> dict[str, Any]:  # noqa: A002 - matches param_schema key
    """P0-style single-shot stub effect for `activate-foundation-c-slice` —
    see `_effect_rotate_key` docstring."""
    return {"runbook": "activate-foundation-c-slice", "slice": slice, "result": "activated"}


RUNBOOK_REGISTRY: dict[str, RunbookSpec] = {
    "activate-signer-service": RunbookSpec(
        name="activate-signer-service",
        required_authority="owner-webauthn",
        risk_class="medium",
        reversible=True,
        declared_effects=("provision-key", "wire-allowlist", "emit-grant", "rebuild"),
        param_schema={"service": {"type": "str", "pattern": SERVICE_NAME_PATTERN}},
        title_template="Activate the {service} service",
        what_template="Lets the system issue signed permits for {service}.",
        why_template="Turns on {service} so it can start signing contexts.",
        effect=_effect_activate_signer_service,
    ),
    "restart-service": RunbookSpec(
        name="restart-service",
        required_authority="owner-webauthn",
        risk_class="low",
        reversible=True,
        declared_effects=("restart",),
        param_schema={"service": {"type": "str", "pattern": SERVICE_NAME_PATTERN}},
        title_template="Restart the {service} service",
        what_template="Restarts {service} to pick up an already-reviewed change.",
        why_template="Applies a pending change to {service} without a full rebuild.",
        effect=_effect_restart_service,
    ),
    # ---- ACP-P3 additions below. Plain-language copy verbatim (title/what/
    # why paraphrased into `{param}`-templated form; impact/reversible taken
    # directly) from the orchestrator-verified local look-ahead lane —
    # `.agents/plans/approval-control-plane/ACP-PREP-COPY-20260816.md`
    # §"Runbook plain-language copy". `activate-signer-service` above is
    # UNCHANGED (its existing risk_class="medium" stays as P0 registered it,
    # even though the prep doc's copy says "high" for its free-text version —
    # changing it here would drift `GOLDEN_CANONICAL_HASH` in
    # `test-approval-request.py`, which this build must not touch).
    "rotate-key": RunbookSpec(
        name="rotate-key",
        required_authority="owner-webauthn",
        risk_class="high",
        reversible=False,
        declared_effects=("generate-key", "update-config", "revoke-old-key", "confirm-sessions"),
        param_schema={"subject": {"type": "str", "pattern": IDENTIFIER_PATTERN}},
        title_template="Rotate the {subject} access key",
        what_template="Generates a new secret key for {subject} and replaces the old one.",
        why_template="Old keys may be compromised or expired; rotating {subject}'s key keeps the system secure.",
        effect=_effect_rotate_key,
    ),
    "epoch-revoke": RunbookSpec(
        name="epoch-revoke",
        required_authority="owner-webauthn",
        risk_class="high",
        reversible=False,
        declared_effects=("identify-epoch", "revoke-epoch", "propagate-revoke", "verify-revoke"),
        param_schema={"epoch_scope": {"type": "str", "pattern": IDENTIFIER_PATTERN}},
        title_template="Revoke all current permits for {epoch_scope}",
        what_template="Instantly invalidates every permission currently held under {epoch_scope}.",
        why_template="Emergency stop to block further action under {epoch_scope} if a security issue is found.",
        effect=_effect_epoch_revoke,
    ),
    "emit-grant": RunbookSpec(
        name="emit-grant",
        required_authority="owner-webauthn",
        risk_class="medium",
        reversible=True,
        declared_effects=("define-scope", "generate-grant-id", "record-grant", "confirm-grant"),
        param_schema={"grant_subject": {"type": "str", "pattern": IDENTIFIER_PATTERN}},
        title_template="Issue a one-time permit for {grant_subject}",
        what_template="Creates a unique, single-use permission for {grant_subject}.",
        why_template="Allows temporary access for {grant_subject} without granting long-term rights.",
        effect=_effect_emit_grant,
    ),
    "activate-foundation-c-slice": RunbookSpec(
        name="activate-foundation-c-slice",
        required_authority="owner-webauthn",
        risk_class="medium",
        reversible=True,
        declared_effects=("check-deps", "load-config", "activate-slice", "verify-health"),
        param_schema={"slice": {"type": "str", "pattern": IDENTIFIER_PATTERN}},
        title_template="Activate the {slice} foundation slice",
        what_template="Turns on the {slice} building block required for base operations.",
        why_template="{slice} must be active before higher-level features can function correctly.",
        effect=_effect_activate_foundation_c_slice,
    ),
}


def _validate_params(spec: RunbookSpec, params: Any) -> Optional[str]:
    """Closed param-schema check: the param keyset must match the runbook's
    registered schema EXACTLY (no missing, no extra — no smuggled fields),
    and every value must satisfy its declared type + optional pattern.
    Returns a `REJECT_*` reason or `None` if well-formed."""
    if not isinstance(params, dict):
        return REJECT_PARAM_TYPE
    allowed = set(spec.param_schema)
    if set(params.keys()) != allowed:
        return REJECT_PARAM_KEYS
    for key, entry in spec.param_schema.items():
        value = params[key]
        kind = entry.get("type")
        if kind == "str":
            if not isinstance(value, str) or not value:
                return REJECT_PARAM_TYPE
            pattern = entry.get("pattern")
            if pattern and re.fullmatch(pattern, value) is None:
                return REJECT_PARAM_PATTERN
        elif kind == "int":
            if not isinstance(value, int) or isinstance(value, bool):
                return REJECT_PARAM_TYPE
        elif kind == "bool":
            if not isinstance(value, bool):
                return REJECT_PARAM_TYPE
        else:  # pragma: no cover - registry misconfiguration, not reachable via caller input
            return REJECT_PARAM_TYPE
    return None


def render_summary(spec: RunbookSpec, params: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic Layer-1 projection of a runbook's typed params (review
    finding #7) — the ONLY way `summary` text is produced. `impact` is the
    runbook's own `risk_class`, never asserted by the caller. `validate()`
    recomputes this and rejects any record whose `summary` does not match
    byte-for-byte, so free-text override is impossible at P0."""
    return {
        "title": spec.title_template.format(**params),
        "what": spec.what_template.format(**params),
        "why": spec.why_template.format(**params),
        "impact": spec.risk_class,
        "reversible": spec.reversible,
    }


# --------------------------------------------------------------------------
# Privacy boundary (design invariant 2) — `summary` MUST contain no hex-64,
# no `/run/secrets`, no filesystem path, no key_id, no socket path, no
# literal "sha256". Checked independently of the template-match check above
# so a bug in a future runbook template (or a hand-crafted record) is still
# caught here, not only by the "not rendered from template" check.
# --------------------------------------------------------------------------

_HEX64_RE = re.compile(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])")
_ABS_PATH_RE = re.compile(r"(?<!\S)/[\w.-]+(?:/[\w.-]+)+")
_SOCKET_RE = re.compile(r"\.sock\b|unix://", re.IGNORECASE)
_KEY_ID_RE = re.compile(r"key[_-]?id", re.IGNORECASE)


def _scan_privacy_leak(text: str) -> Optional[str]:
    """First-match-wins scan of plain-language text for anything that
    belongs only in `technical_trail` (Layer 3). Returns a `LEAK_*` reason
    or `None` if clean."""
    if _HEX64_RE.search(text):
        return LEAK_HEX64
    if "/run/secrets" in text:
        return LEAK_RUN_SECRETS
    if _ABS_PATH_RE.search(text):
        return LEAK_FILESYSTEM_PATH
    if _KEY_ID_RE.search(text):
        return LEAK_KEY_ID
    if _SOCKET_RE.search(text):
        return LEAK_SOCKET_PATH
    if "sha256" in text.lower():
        return LEAK_SHA256_LITERAL
    return None


# --------------------------------------------------------------------------
# Canonicalization + hash (design invariant 4, refined by review finding #8)
# --------------------------------------------------------------------------

# `canonical_hash` covers every CONTENT field — summary + required_authority +
# action_manifest + technical_trail — PLUS the immutable instance id
# `request_id`, and EXCLUDES `binding` + the mutable/derivable envelope fields
# `schema`/`created_at`/`created_by`/`status`.
#
# `status` MUST stay excluded: it moves through the state machine
# (`transition()`) *after* creation, and the whole point of this hash is that
# the executor can recompute-and-compare it at every stage (pending -> approved
# -> executed) without it drifting just because `status` changed.
#
# `request_id` MUST be INCLUDED (ACP-P1 Antigravity review finding 2, CRITICAL,
# verified). It is write-once/immutable after creation, so it never causes the
# recompute-drift that `status` would. Binding it into the signed content makes
# the owner signature unique to THIS request instance: without it, two distinct
# requests with identical content share a `canonical_hash`, so one human
# approval's Ed25519 signature would be replayable against a content-identical
# sibling request (different `request_id`, never itself approved). Including
# `request_id` here — combined with the request_id-keyed single-use ledger and
# the append-only executed-request ledger (P1) — closes cross-request signature
# reuse. `created_at`/`created_by` stay out: not needed for instance-binding and
# `created_at` complicates deterministic golden fixtures.
CANONICAL_FIELDS = ("request_id", "summary", "required_authority", "action_manifest", "technical_trail")

# Domain-separates this hash from any other canonical-payload family in the
# codebase (mirrors `revocation_epoch.DOMAIN_TAG`) even if a field set
# happened to collide.
DOMAIN_TAG = b"aq.approval-request.v1"


def _as_dict(record: Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(record, dict):
        return record
    if isinstance(record, Mapping):
        return dict(record)
    raise TypeError(f"unsupported record type: {type(record)!r}")


def canonicalize(record: Mapping[str, Any]) -> bytes:
    """Deterministic canonical bytes over the record's immutable CONTENT
    fields only (`CANONICAL_FIELDS` — see the module-level note above for
    why `binding` AND the envelope fields are excluded). Sorted keys, no
    whitespace (`separators=(',', ':')`), UTF-8, `ensure_ascii=False` — same
    machine on any run, any field-insertion order, produces byte-identical
    output. This is the exact byte string `compute_hash` hashes and the one
    a later WebAuthn signer (P1) would sign."""
    data = _as_dict(record)
    content = {field: data.get(field) for field in CANONICAL_FIELDS}
    body = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return DOMAIN_TAG + b"\x00" + body


def compute_hash(record: Mapping[str, Any]) -> str:
    """sha256 hex digest of `canonicalize(record)`."""
    return hashlib.sha256(canonicalize(record)).hexdigest()


# --------------------------------------------------------------------------
# Time helpers (mirrors `revocation_epoch`/`capability_lease`)
# --------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _now_iso() -> str:
    return _iso(datetime.now(timezone.utc))


def _parse_iso(value: str) -> datetime:
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# --------------------------------------------------------------------------
# validate() — total function, never raises, never acts (design invariants
# 1-3, review findings #7-#8)
# --------------------------------------------------------------------------


def validate(record: Any) -> ValidationVerdict:
    """Typed, report-only, total verdict over a full `aq.approval-request.v1`
    record. Check order (first match wins): shape/closed-schema -> envelope
    fields -> summary schema -> privacy-leak scan -> required_authority ->
    action_manifest schema -> runbook registration -> param schema ->
    declared_effects/required_authority bound to the registry -> summary
    matches the registry's deterministic rendering -> technical_trail schema
    -> binding schema -> ok. Never raises; never mutates `record`."""
    try:
        if not isinstance(record, dict):
            return ValidationVerdict(False, REJECT_NOT_A_MAPPING)
        if set(record.keys()) != TOP_LEVEL_KEYS:
            return ValidationVerdict(False, REJECT_TOP_LEVEL_SCHEMA, f"keys={sorted(record.keys())}")
        if record.get("schema") != SCHEMA_ID:
            return ValidationVerdict(False, REJECT_SCHEMA_ID, str(record.get("schema")))

        for field in ("request_id", "created_by"):
            value = record.get(field)
            if not isinstance(value, str) or not value:
                return ValidationVerdict(False, REJECT_ENVELOPE_FIELD, field)
        created_at = record.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            return ValidationVerdict(False, REJECT_ENVELOPE_FIELD, "created_at")
        try:
            _parse_iso(created_at)
        except (TypeError, ValueError):
            return ValidationVerdict(False, REJECT_ENVELOPE_FIELD, "created_at")

        status = record.get("status")
        if status not in STATUSES:
            return ValidationVerdict(False, REJECT_UNKNOWN_STATUS, str(status))

        summary = record.get("summary")
        if not isinstance(summary, dict) or set(summary.keys()) != SUMMARY_KEYS:
            return ValidationVerdict(False, REJECT_SUMMARY_SCHEMA, "shape")
        title = summary.get("title")
        what = summary.get("what")
        why = summary.get("why")
        impact = summary.get("impact")
        reversible = summary.get("reversible")
        if not isinstance(title, str) or not (1 <= len(title) <= MAX_TITLE_LEN):
            return ValidationVerdict(False, REJECT_SUMMARY_SCHEMA, "title")
        if not isinstance(what, str) or not what:
            return ValidationVerdict(False, REJECT_SUMMARY_SCHEMA, "what")
        if not isinstance(why, str) or not why:
            return ValidationVerdict(False, REJECT_SUMMARY_SCHEMA, "why")
        if impact not in IMPACT_LEVELS:
            return ValidationVerdict(False, REJECT_SUMMARY_SCHEMA, "impact")
        if not isinstance(reversible, bool):
            return ValidationVerdict(False, REJECT_SUMMARY_SCHEMA, "reversible")

        leak = _scan_privacy_leak("\n".join((title, what, why)))
        if leak is not None:
            return ValidationVerdict(False, leak)

        authority = record.get("required_authority")
        if authority not in REQUIRED_AUTHORITY_VALUES:
            return ValidationVerdict(False, REJECT_REQUIRED_AUTHORITY, str(authority))

        manifest = record.get("action_manifest")
        if not isinstance(manifest, dict) or set(manifest.keys()) != ACTION_MANIFEST_KEYS:
            return ValidationVerdict(False, REJECT_ACTION_MANIFEST_SCHEMA, "shape")
        runbook = manifest.get("runbook")
        spec = RUNBOOK_REGISTRY.get(runbook) if isinstance(runbook, str) else None
        if spec is None:
            return ValidationVerdict(False, REJECT_UNKNOWN_RUNBOOK, str(runbook))

        params = manifest.get("params")
        param_reason = _validate_params(spec, params)
        if param_reason is not None:
            return ValidationVerdict(False, param_reason, runbook)

        declared = manifest.get("declared_effects")
        if declared != list(spec.declared_effects):
            return ValidationVerdict(False, REJECT_DECLARED_EFFECTS_MISMATCH, runbook)
        if authority != spec.required_authority:
            return ValidationVerdict(False, REJECT_REQUIRED_AUTHORITY_MISMATCH, runbook)

        expected_summary = render_summary(spec, params)
        if summary != expected_summary:
            return ValidationVerdict(False, REJECT_SUMMARY_MISMATCH, runbook)

        trail = record.get("technical_trail")
        if not isinstance(trail, dict) or set(trail.keys()) != TECHNICAL_TRAIL_KEYS:
            return ValidationVerdict(False, REJECT_TECHNICAL_TRAIL_SCHEMA, "shape")
        if not isinstance(trail.get("design_sha256"), str):
            return ValidationVerdict(False, REJECT_TECHNICAL_TRAIL_SCHEMA, "design_sha256")
        target_files = trail.get("target_files")
        if not isinstance(target_files, list) or not all(isinstance(x, str) for x in target_files):
            return ValidationVerdict(False, REJECT_TECHNICAL_TRAIL_SCHEMA, "target_files")
        if not isinstance(trail.get("grant_subject"), str):
            return ValidationVerdict(False, REJECT_TECHNICAL_TRAIL_SCHEMA, "grant_subject")

        binding = record.get("binding")
        if not isinstance(binding, dict) or set(binding.keys()) != BINDING_KEYS:
            return ValidationVerdict(False, REJECT_BINDING_SCHEMA, "shape")
        canonical_hash = binding.get("canonical_hash")
        if not isinstance(canonical_hash, str) or re.fullmatch(r"[0-9a-f]{64}", canonical_hash) is None:
            return ValidationVerdict(False, REJECT_BINDING_SCHEMA, "canonical_hash")
        requester_sig = binding.get("requester_sig")
        if requester_sig is not None and not isinstance(requester_sig, str):
            return ValidationVerdict(False, REJECT_BINDING_SCHEMA, "requester_sig")

        return ValidationVerdict(True, VERIFY_OK)
    except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
        return ValidationVerdict(False, REJECT_INTERNAL, f"unhandled:{exc.__class__.__name__}")


# --------------------------------------------------------------------------
# Builder — raises on a malformed request (build-time, not a verify path)
# --------------------------------------------------------------------------


def create_request(
    *,
    request_id: str,
    created_by: str,
    runbook: str,
    params: Mapping[str, Any],
    target_files: Optional[list] = None,
    grant_subject: str = "",
    design_sha256: str = "",
    created_at: Optional[str] = None,
) -> dict[str, Any]:
    """Build a fresh, valid, `pending` `aq.approval-request.v1` record.
    `summary` and `required_authority` are derived entirely from the
    registered runbook's spec + the caller's typed `params` — never taken
    from the caller directly (review finding #7). Raises
    `ApprovalValidationError` if `runbook` is unregistered, `params` fails
    the runbook's own param schema, or the assembled record fails
    `validate()` for any other reason (defense in depth — should not happen
    if the above two checks pass)."""
    spec = RUNBOOK_REGISTRY.get(runbook)
    if spec is None:
        raise ApprovalValidationError(REJECT_UNKNOWN_RUNBOOK, str(runbook))
    param_reason = _validate_params(spec, params)
    if param_reason is not None:
        raise ApprovalValidationError(param_reason, runbook)

    summary = render_summary(spec, params)
    record: dict[str, Any] = {
        "schema": SCHEMA_ID,
        "request_id": request_id,
        "created_at": created_at or _now_iso(),
        "created_by": created_by,
        "status": STATUS_PENDING,
        "summary": summary,
        "required_authority": spec.required_authority,
        "action_manifest": {
            "runbook": runbook,
            "params": dict(params),
            "declared_effects": list(spec.declared_effects),
        },
        "technical_trail": {
            "design_sha256": design_sha256,
            "target_files": list(target_files or []),
            "grant_subject": grant_subject,
        },
        "binding": {"canonical_hash": "", "requester_sig": None},
    }
    record["binding"]["canonical_hash"] = compute_hash(record)

    verdict = validate(record)
    if not verdict.ok:
        raise ApprovalValidationError(verdict.reason, verdict.detail)
    return record


# --------------------------------------------------------------------------
# State machine (design invariant 5)
# --------------------------------------------------------------------------


def transition(
    record: Mapping[str, Any],
    new_status: str,
    *,
    actor: str,
    now: Optional[datetime] = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Move `record` from its current `status` to `new_status`. Raises
    `ApprovalStateError` if `record` does not currently `validate()`, or if
    `current_status -> new_status` is not in `ALLOWED_TRANSITIONS` — no
    other transition is possible, and an illegal one produces NEITHER a new
    record NOR an event (fail closed). A legal transition returns
    `(new_record, event)`: `new_record` is a shallow copy of `record` with
    only `status` changed (every `CANONICAL_FIELDS` entry — and therefore
    `binding.canonical_hash` — is untouched, by design; see `canonicalize`'s
    docstring), and `event` is the audited transition record."""
    verdict = validate(record)
    if not verdict.ok:
        raise ApprovalStateError(REJECT_INVALID_RECORD, verdict.reason)

    current = record["status"]
    if new_status not in STATUSES or new_status not in ALLOWED_TRANSITIONS.get(current, frozenset()):
        raise ApprovalStateError(REJECT_ILLEGAL_TRANSITION, f"{current}->{new_status}")

    moment = now or datetime.now(timezone.utc)
    new_record = dict(record)
    new_record["status"] = new_status
    event = {
        "event": "approval_state_transition",
        "request_id": record["request_id"],
        "from_status": current,
        "to_status": new_status,
        "actor": actor,
        "at": _iso(moment),
    }
    return new_record, event
