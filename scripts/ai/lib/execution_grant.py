"""ExecutionGrant primitive — Foundation C, C3b R1 (pure, offline, deny-closed).

Implements ONLY the pure functions authorized by
`.agents/plans/aqos-foundation-c/C3B-R1-DESIGN-AND-AUTHORIZATION.md`
(status R1_REVIEWED_PASS): the closed execution-grant schema, Ed25519
verify-only signature checking, freshness/epoch/replay verification, and
multi-effect + trusted-path classification. This module opens NO socket,
performs NO git clone, invokes NO bwrap, touches NO Nix/systemd surface,
and does NO filesystem I/O of its own — it is a pure library consumed by
later (not-yet-authorized) R2+ stages. `verify_grant()` NEVER raises and
NEVER acts; it only reports a typed, immutable verdict.

The execution grant is a NEW artifact distinct from `capability_lease`'s
CapabilityLease: it is a signed projection of a verified lease plus
execution-cell-specific fields, minted by C2's gate at admission time (a
later, not-yet-authorized slice). This module reuses `capability_lease`'s
canonical-serialization discipline (recursive sorted keys, every field
except `signature`, stable UTF-8 JSON — see `canonical_payload` below) but
does NOT reuse its symmetric HMAC sign/verify. See design §3 (SF-1): the
cell runner is a new privileged boundary (it alone gets userns to build
cells), so a compromised runner must not be able to forge a grant. With
symmetric HMAC the verifier needs the signing key; with Ed25519 the
gate/issuer alone holds the PRIVATE key (SOPS `/run/secrets/`, later
slice) and the runner holds only the non-secret PUBLIC verify key. This
module's PRODUCTION surface is therefore verify-only
(`verify_signature`/`verify_grant`, taking a public key). `sign()` exists
purely so tests/fixture generation can produce genuinely-signed golden
vectors offline — production code must never call it with a runner-held
key (there is no such key to hold; the runner never possesses a private
key at all).

Epoch source: R1 freezes `capability_lease_gate.resolve_current_epoch`
(`ai-stack/switchboard/capability_lease_gate.py:172`) reading
`config/capability-lease-epoch` (`DEFAULT_EPOCH_PATH`, line 84) as its
authoritative dependency. This module does NOT import that runtime state
itself — `verify_epoch`/`verify_grant` take `current_epoch: int | None` as
an explicit parameter; the caller is responsible for resolving it via that
frozen API. `current_epoch is None` always denies (`stale-epoch`) — the
staleness check is never skipped.
"""

from __future__ import annotations

import hashlib
import json
import re
import types
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional, Union

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

# --------------------------------------------------------------------------
# Typed result vocabulary (deny-closed; every verb below is a total
# function — see each docstring for its exact never-raise contract).
# --------------------------------------------------------------------------

VERIFY_OK = "ok"

DENY_MALFORMED = "grant-malformed"
DENY_BAD_SIGNATURE = "bad-signature"
DENY_EXPIRED = "expired"
DENY_NOT_YET_VALID = "not-yet-valid"
DENY_UNKNOWN_VERSION = "unknown-version"
DENY_STALE_EPOCH = "stale-epoch"
DENY_REPLAYED = "replayed"
DENY_CLASSIFICATION_AMBIGUOUS = "classification-ambiguous"
DENY_PATH_INVALID = "path-invalid"

REPLAY_RESERVED = "reserved"
REPLAY_REPLAYED = "replayed"
RESERVATION_RESERVED = "reserved"
RESERVATION_COMMITTED = "committed"
RESERVATION_FAILED = "failed"


# --------------------------------------------------------------------------
# Closed schema (design §2)
# --------------------------------------------------------------------------

GRANT_SCHEMA_VERSIONS: frozenset[int] = frozenset({1})

REQUIRED_GRANT_FIELDS: tuple[str, ...] = (
    "grant_schema_version",
    "grant_id",
    "lease_id",
    "task_id",
    "request_id",
    "issued_at",
    "expires_at",
    "revocation_epoch",
    "base_revision",
    "effect_set",
    "exec_class",
    "trusted_repo_id",
    "logical_paths",
    "resource_limits",
    "grant_digest",
    "signature",
)

REQUIRED_RESOURCE_LIMIT_FIELDS: tuple[str, ...] = ("timeout_s", "max_output_bytes", "cell_class")

# `unsandboxed-authorized` is deliberately NOT a member — design §2:
# "unsandboxed-authorized NOT accepted in C3b".
EXEC_CLASSES: frozenset[str] = frozenset({"none", "sandbox-required"})

# Design §4.1 closed vocabulary.
ALLOWED_CLASS_EFFECTS: frozenset[str] = frozenset({"read", "deterministic-validate", "write", "subprocess"})
DENY_CLASS_EFFECTS: frozenset[str] = frozenset({
    "network", "delegate", "secret", "device", "mount", "privilege",
    "host-process", "arbitrary-env",
})
KNOWN_EFFECTS: frozenset[str] = ALLOWED_CLASS_EFFECTS | DENY_CLASS_EFFECTS

# ≥128-bit collision resistance for the replay-reservation key (design §2).
MIN_GRANT_ID_LEN = 32

_HEX40_OR_64 = re.compile(r"^([0-9a-f]{40}|[0-9a-f]{64})$")
# Bounded charset + minimum length (antigravity SHOULD-FIX, design §2): a
# blank/whitespace trusted_repo_id must never validate, so it can never be
# passed as a bypass target into R2.
_TRUSTED_REPO_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,255}$")

_CONTROL_CHARS: frozenset[str] = frozenset(chr(c) for c in range(0x00, 0x20)) | {chr(0x7F)}
# Unicode bidi-override / directional-formatting characters: a real-world
# path-spoofing vector (visually reorders a path's rendered form) — R1
# treats their presence as a symlink/escape-style marker per design §4.2's
# "any symlink-escape marker" clause, since no real filesystem resolution
# is available yet to detect an actual symlink.
_BIDI_OVERRIDE_CHARS: frozenset[str] = frozenset({
    "‎", "‏", "‪", "‫", "‬", "‭", "‮",
    "⁦", "⁧", "⁨", "⁩",
})


# --------------------------------------------------------------------------
# Typed dataclasses
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Denial:
    """A typed, terminal deny verdict. `reason` is one of the DENY_*
    constants above; `detail` is a human-readable (never security-bearing)
    explanation for logs/tests, not for programmatic branching."""

    reason: str
    detail: str = ""


@dataclass(frozen=True)
class EffectScope:
    effect: str
    scope: "types.MappingProxyType[str, Any]"


@dataclass(frozen=True)
class Classification:
    """Result of `classify_effects` — every element already proven to be a
    known, non-deny-class, non-contradictory, non-duplicated effect."""

    effects: tuple[EffectScope, ...]


@dataclass(frozen=True)
class PathPlan:
    """Result of `classify_paths` — every requested path already proven
    syntactically safe and component-contained under the allowlist. Real
    filesystem resolution (symlinks, existence, cell-root rebasing) is
    R2/R3; this is a pure, syntactic plan only."""

    allowlist: tuple[str, ...]
    entries: tuple[tuple[str, tuple[str, ...]], ...]  # (original_path, components)


@dataclass(frozen=True)
class VerifiedGrant:
    """The SOLE object later (not-yet-authorized) stages accept — mirrors
    C3a's per-tool verified context. Immutable; only `verify_grant` can
    construct one, and only on an all-pass composition of every check in
    §5/§8-7's fixed order."""

    grant_id: str
    lease_id: str
    task_id: str
    request_id: str
    base_revision: str
    exec_class: str
    trusted_repo_id: str
    resource_limits: "types.MappingProxyType[str, Any]"
    grant_digest: str
    classification: Classification
    path_plan: PathPlan
    raw: "types.MappingProxyType[str, Any]"


VerifyResult = Union[VerifiedGrant, Denial]


# --------------------------------------------------------------------------
# Canonical serialization + digest (mirrors capability_lease.canonical_payload)
# --------------------------------------------------------------------------


def canonical_payload(grant: dict) -> bytes:
    """Deterministic JSON over every grant field EXCEPT `signature` —
    sorted keys, no whitespace (separators=(',', ':')), UTF-8,
    ensure_ascii=False. This is the exact byte string that gets
    Ed25519-signed. It includes `grant_digest` as one of the signed
    fields, so a tampered `grant_digest` is itself caught by signature
    verification exactly like any other field."""
    signable = {k: v for k, v in grant.items() if k != "signature"}
    return json.dumps(signable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_grant_digest(grant: dict) -> str:
    """SHA-256 hex digest over every grant field except `signature` AND
    `grant_digest` itself (a digest cannot include its own value). Bound
    into the signed payload as the `grant_digest` field, so signature
    verification transitively covers it too — this is a fast, independent
    tamper-evidence check that doesn't require running Ed25519 to fail
    loudly on a mismatched digest."""
    signable = {k: v for k, v in grant.items() if k not in ("signature", "grant_digest")}
    payload = json.dumps(signable, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


# --------------------------------------------------------------------------
# Signing (TEST-ONLY) — see module docstring. Production never calls this.
# --------------------------------------------------------------------------


def generate_keypair() -> tuple[Ed25519PrivateKey, bytes]:
    """TEST-ONLY: a fresh Ed25519 keypair for golden-vector / fixture
    generation. Returns (private_key, public_key_bytes). Production code
    never calls this — the gate/issuer's private key is provisioned via
    SOPS by a later slice, never generated ad hoc here."""
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private_key, public_bytes


def sign(grant: dict, private_key: Ed25519PrivateKey) -> dict:
    """TEST-ONLY signer for golden-vector generation (design §3: "a
    dev/test key, if used, is a distinct public key the production runner
    does NOT trust"). Builds `grant_digest`, signs the canonical payload,
    and returns a NEW dict with both populated. NOT part of the production
    surface: the runner holds only a public key and must never be able to
    mint a grant, so this module exposes no path that signs with a
    runner-held key. `grant` need not already contain `grant_digest`/
    `signature` — both are recomputed."""
    base = {k: v for k, v in grant.items() if k not in ("grant_digest", "signature")}
    digest = compute_grant_digest(base)
    with_digest = {**base, "grant_digest": digest}
    payload = canonical_payload(with_digest)
    signature = private_key.sign(payload)
    return {**with_digest, "signature": signature.hex()}


# --------------------------------------------------------------------------
# Schema validation — closed, no defaulting (design §2)
# --------------------------------------------------------------------------


def _is_strict_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _parse_rfc3339(value: str) -> datetime:
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def validate_grant_schema(grant: Any) -> Union[dict, Denial]:
    """Closed-schema structural/type validation (design §2). The field set
    must be EXACT (no missing, no unknown extras) and every field's type/
    format must match its invariant. Never raises — any failure is a typed
    `grant-malformed` Denial. On success, returns the SAME dict (not a
    copy) so callers can keep using ordinary dict access on it."""
    try:
        if not isinstance(grant, dict):
            return Denial(DENY_MALFORMED, "grant is not a JSON object")

        fields = set(grant.keys())
        required = set(REQUIRED_GRANT_FIELDS)
        if fields != required:
            missing = sorted(required - fields)
            unknown = sorted(fields - required)
            parts = []
            if missing:
                parts.append(f"missing={missing}")
            if unknown:
                parts.append(f"unknown={unknown}")
            return Denial(DENY_MALFORMED, "closed-schema field-set mismatch: " + "; ".join(parts))

        if not _is_strict_int(grant["grant_schema_version"]):
            return Denial(DENY_MALFORMED, "grant_schema_version must be an int")

        for str_field in (
            "grant_id", "lease_id", "task_id", "request_id", "issued_at",
            "expires_at", "base_revision", "exec_class", "trusted_repo_id",
            "grant_digest", "signature",
        ):
            value = grant[str_field]
            if not isinstance(value, str) or not value:
                return Denial(DENY_MALFORMED, f"{str_field} must be a non-empty string")

        if len(grant["grant_id"]) < MIN_GRANT_ID_LEN:
            return Denial(DENY_MALFORMED, "grant_id below minimum collision-resistant length")

        if not _is_strict_int(grant["revocation_epoch"]):
            return Denial(DENY_MALFORMED, "revocation_epoch must be an int")

        if not _HEX40_OR_64.match(grant["base_revision"]):
            return Denial(DENY_MALFORMED, "base_revision must be a full 40- or 64-hex git OID")

        if grant["exec_class"] not in EXEC_CLASSES:
            return Denial(DENY_MALFORMED, f"exec_class must be one of {sorted(EXEC_CLASSES)}")

        # Blank/whitespace trusted_repo_id must deny — never usable as an
        # R2 bypass target (antigravity SHOULD-FIX, design §2).
        if not grant["trusted_repo_id"].strip() or not _TRUSTED_REPO_ID_RE.match(grant["trusted_repo_id"]):
            return Denial(DENY_MALFORMED, "trusted_repo_id blank or syntactically invalid")

        effect_set = grant["effect_set"]
        if not isinstance(effect_set, list) or not effect_set:
            return Denial(DENY_MALFORMED, "effect_set must be a non-empty list")
        for item in effect_set:
            if not isinstance(item, dict) or set(item.keys()) != {"effect", "scope"}:
                return Denial(DENY_MALFORMED, "effect_set entries must be exactly {effect, scope}")
            if not isinstance(item["effect"], str) or not item["effect"]:
                return Denial(DENY_MALFORMED, "effect_set entry 'effect' must be a non-empty string")
            if not isinstance(item["scope"], dict):
                return Denial(DENY_MALFORMED, "effect_set entry 'scope' must be an object")

        logical_paths = grant["logical_paths"]
        if (
            not isinstance(logical_paths, list)
            or not logical_paths
            or not all(isinstance(p, str) and p for p in logical_paths)
        ):
            return Denial(DENY_MALFORMED, "logical_paths must be a non-empty list of non-empty strings")

        resource_limits = grant["resource_limits"]
        if not isinstance(resource_limits, dict) or set(resource_limits.keys()) != set(REQUIRED_RESOURCE_LIMIT_FIELDS):
            return Denial(DENY_MALFORMED, "resource_limits must be exactly {timeout_s, max_output_bytes, cell_class}")
        timeout_s = resource_limits["timeout_s"]
        max_output_bytes = resource_limits["max_output_bytes"]
        cell_class = resource_limits["cell_class"]
        if not _is_strict_int(timeout_s) or timeout_s <= 0:
            return Denial(DENY_MALFORMED, "resource_limits.timeout_s must be a positive int")
        if not _is_strict_int(max_output_bytes) or max_output_bytes <= 0:
            return Denial(DENY_MALFORMED, "resource_limits.max_output_bytes must be a positive int")
        if not isinstance(cell_class, str) or not cell_class:
            return Denial(DENY_MALFORMED, "resource_limits.cell_class must be a non-empty string")

        try:
            issued_at = _parse_rfc3339(grant["issued_at"])
            expires_at = _parse_rfc3339(grant["expires_at"])
        except (ValueError, TypeError):
            return Denial(DENY_MALFORMED, "issued_at/expires_at must be RFC3339 UTC timestamps")
        if expires_at <= issued_at:
            return Denial(DENY_MALFORMED, "expires_at must be after issued_at")

        return grant
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return Denial(DENY_MALFORMED, f"internal schema-validation error: {type(exc).__name__}: {exc}")


# --------------------------------------------------------------------------
# Verification pure functions (design §5) — deny-closed, never raise.
# --------------------------------------------------------------------------


def verify_signature(grant: Any, public_key_bytes: bytes) -> str:
    """Ed25519 verify-only (PRODUCTION surface): recomputes `grant_digest`
    and compares it, then verifies the Ed25519 signature over
    `canonical_payload(grant)` using ONLY the supplied public key bytes.
    Never raises: any malformed input, bad hex, or `InvalidSignature`
    collapses to `bad-signature`."""
    try:
        if not isinstance(grant, dict):
            return DENY_BAD_SIGNATURE
        expected_digest = compute_grant_digest(grant)
        actual_digest = grant.get("grant_digest")
        if not isinstance(actual_digest, str) or actual_digest != expected_digest:
            return DENY_BAD_SIGNATURE
        sig_hex = grant.get("signature")
        if not isinstance(sig_hex, str):
            return DENY_BAD_SIGNATURE
        signature_bytes = bytes.fromhex(sig_hex)
        payload = canonical_payload(grant)
        public_key = Ed25519PublicKey.from_public_bytes(public_key_bytes)
        public_key.verify(signature_bytes, payload)
        return VERIFY_OK
    except Exception:
        return DENY_BAD_SIGNATURE


def verify_freshness(grant: Any, now: Optional[datetime] = None) -> str:
    """Half-open `[issued_at, expires_at)` freshness check. Never raises."""
    try:
        moment = now if now is not None else datetime.now(timezone.utc)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        else:
            moment = moment.astimezone(timezone.utc)
        issued_at = _parse_rfc3339(grant["issued_at"])
        expires_at = _parse_rfc3339(grant["expires_at"])
        if moment < issued_at:
            return DENY_NOT_YET_VALID
        if moment >= expires_at:
            return DENY_EXPIRED
        return VERIFY_OK
    except Exception:
        return DENY_MALFORMED


def verify_schema_version(grant: Any) -> str:
    """Closed known-version set — unknown version never guessed forward-
    compatible. Never raises."""
    try:
        version = grant.get("grant_schema_version") if isinstance(grant, dict) else None
        if _is_strict_int(version) and version in GRANT_SCHEMA_VERSIONS:
            return VERIFY_OK
        return DENY_UNKNOWN_VERSION
    except Exception:
        return DENY_UNKNOWN_VERSION


def verify_epoch(grant: Any, current_epoch: Optional[int]) -> str:
    """Authoritative source (frozen dependency, see module docstring):
    `capability_lease_gate.resolve_current_epoch` /
    `config/capability-lease-epoch`. `current_epoch is None` (unresolvable
    epoch source) ALWAYS denies — the staleness check is never skipped.
    Never raises."""
    try:
        if current_epoch is None or not _is_strict_int(current_epoch):
            return DENY_STALE_EPOCH
        if not isinstance(grant, dict):
            return DENY_STALE_EPOCH
        revocation_epoch = grant.get("revocation_epoch")
        if not _is_strict_int(revocation_epoch):
            return DENY_STALE_EPOCH
        if revocation_epoch < current_epoch:
            return DENY_STALE_EPOCH
        return VERIFY_OK
    except Exception:
        return DENY_STALE_EPOCH


# --------------------------------------------------------------------------
# Replay reservation — pure INTERFACE only (design §5). The durable store
# is R3; this defines the contract + in-memory reference implementation
# for tests, NOT a production persistence layer.
# --------------------------------------------------------------------------


class ReplayReservationSet:
    """Pure, in-memory REFERENCE implementation of the replay-reservation
    contract. NOT durable and NOT safe across separate processes — a
    test/reference double only. R3 replaces the backing store with a real
    atomic/durable implementation behind the SAME `try_reserve`/`commit`/
    `fail` contract; callers written against this contract do not change
    when R3 lands. Uniqueness domain is `grant_id`, GLOBAL (never
    task-scoped, design §5/§8-3)."""

    def __init__(self) -> None:
        self._state: dict[str, str] = {}

    def __contains__(self, grant_id: str) -> bool:
        return grant_id in self._state

    def add(self, grant_id: str) -> None:
        """Duck-typed MutableSet.add(), used by `reserve_replay`'s
        set-fallback branch. Equivalent to a bare try_reserve with no
        distinct later commit/fail transition."""
        self._state.setdefault(grant_id, RESERVATION_RESERVED)

    def try_reserve(self, grant_id: str) -> bool:
        """Atomic (within this single-process reference store) try-reserve:
        True iff this call is the first to reserve `grant_id`."""
        if grant_id in self._state:
            return False
        self._state[grant_id] = RESERVATION_RESERVED
        return True

    def commit(self, grant_id: str) -> bool:
        """reserved -> committed. False (no-op) if `grant_id` was never
        reserved, or is already in a terminal state — fail-closed: a
        caller cannot commit what it never reserved, nor double-transition
        a terminal reservation."""
        if self._state.get(grant_id) != RESERVATION_RESERVED:
            return False
        self._state[grant_id] = RESERVATION_COMMITTED
        return True

    def fail(self, grant_id: str) -> bool:
        """reserved -> failed. Same guard as `commit`."""
        if self._state.get(grant_id) != RESERVATION_RESERVED:
            return False
        self._state[grant_id] = RESERVATION_FAILED
        return True

    def state_of(self, grant_id: str) -> Optional[str]:
        return self._state.get(grant_id)


ReservationInterface = Any  # ReplayReservationSet | Callable[[str], bool] | MutableSet-like


def reserve_replay(grant_id: Any, reservation_set: ReservationInterface) -> str:
    """Pure replay-reservation INTERFACE (design §5/§8-3). `reservation_set`
    may be:
      - an object exposing `.try_reserve(grant_id) -> bool` (preferred —
        e.g. `ReplayReservationSet`, or R3's durable store behind the same
        method name);
      - a bare callable `reservation_set(grant_id) -> bool`;
      - a duck-typed MutableSet (`__contains__` + `add`).
    Returns `"reserved"` (this call is the first to see `grant_id` — the
    caller may later transition it to committed/failed via the same
    object, which this function does not itself model) or `"replayed"`
    (`grant_id` already reserved). Uniqueness domain is `grant_id`
    GLOBALLY, never task-scoped. Never raises: any interface error is
    reported as `"replayed"` — an unreliable reservation store must fail
    closed, never silently allow a replay through."""
    try:
        if not isinstance(grant_id, str) or not grant_id:
            return REPLAY_REPLAYED
        try_reserve = getattr(reservation_set, "try_reserve", None)
        if callable(try_reserve):
            return REPLAY_RESERVED if bool(try_reserve(grant_id)) else REPLAY_REPLAYED
        if callable(reservation_set):
            return REPLAY_RESERVED if bool(reservation_set(grant_id)) else REPLAY_REPLAYED
        if grant_id in reservation_set:
            return REPLAY_REPLAYED
        reservation_set.add(grant_id)
        return REPLAY_RESERVED
    except Exception:
        return REPLAY_REPLAYED


# --------------------------------------------------------------------------
# Classification (design §4) — pure, no filesystem/config access.
# --------------------------------------------------------------------------


def classify_effects(effect_set: Any) -> Union[Classification, Denial]:
    """Design §4.1. `effect_set` must be a non-empty list of
    `{"effect": str, "scope": dict}` objects. Unknown / omitted /
    duplicated / contradictory (e.g. a `write` effect whose scope declares
    `mode: "read"`) / any deny-class effect (network, delegate, secret,
    device, mount, privilege, host-process, arbitrary-env) -> typed
    `classification-ambiguous` deny (conservative). Never raises."""
    try:
        if not isinstance(effect_set, (list, tuple)) or not effect_set:
            return Denial(DENY_CLASSIFICATION_AMBIGUOUS, "effect_set missing or empty")

        seen: set[str] = set()
        parsed: list[EffectScope] = []
        for item in effect_set:
            if not isinstance(item, dict):
                return Denial(DENY_CLASSIFICATION_AMBIGUOUS, "effect_set entry is not an object")
            effect = item.get("effect")
            scope = item.get("scope")
            if not isinstance(effect, str) or effect not in KNOWN_EFFECTS:
                return Denial(DENY_CLASSIFICATION_AMBIGUOUS, f"unknown effect {effect!r}")
            if effect in seen:
                return Denial(DENY_CLASSIFICATION_AMBIGUOUS, f"duplicated effect {effect!r}")
            seen.add(effect)
            if effect in DENY_CLASS_EFFECTS:
                return Denial(DENY_CLASSIFICATION_AMBIGUOUS, f"deny-class effect present: {effect!r}")
            if not isinstance(scope, dict):
                return Denial(DENY_CLASSIFICATION_AMBIGUOUS, f"effect {effect!r} missing a scope object")

            mode = scope.get("mode")
            if effect == "write" and mode == "read":
                return Denial(DENY_CLASSIFICATION_AMBIGUOUS, "contradictory: write effect on a read-only scope")
            if effect in ("read", "deterministic-validate") and mode == "write":
                return Denial(DENY_CLASSIFICATION_AMBIGUOUS, f"contradictory: {effect} effect on a write-only scope")

            parsed.append(EffectScope(effect=effect, scope=types.MappingProxyType(dict(scope))))

        return Classification(effects=tuple(parsed))
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return Denial(DENY_CLASSIFICATION_AMBIGUOUS, f"internal classification error: {type(exc).__name__}: {exc}")


def _split_components(path: str) -> list[str]:
    return [c for c in path.split("/") if c != ""]


def _validate_path_syntax(paths: Any, label: str) -> Union[list[str], Denial]:
    """Shared per-path syntactic gate (design §4.2), applied to BOTH the
    allowlist and the requested paths — either list could carry an attack
    payload. Checks: type, absolute host path, symlink-escape markers
    (backslash alt-separator, Unicode bidi-override), NUL/control bytes,
    non-NFC Unicode normalization (`unicodedata.is_normalized`, per
    design's explicit "NOT a custom regex" instruction). Traversal (`..`)
    and casefold/containment checks are structural (need the FULL list, or
    the allowlist) and are done by the caller."""
    if not isinstance(paths, (list, tuple)):
        return Denial(DENY_PATH_INVALID, f"{label} is not a list")
    out: list[str] = []
    for path in paths:
        if not isinstance(path, str) or not path:
            return Denial(DENY_PATH_INVALID, f"{label} entry is not a non-empty string")
        if path.startswith("/"):
            return Denial(DENY_PATH_INVALID, f"absolute host path in {label}: {path!r}")
        if "\\" in path:
            return Denial(DENY_PATH_INVALID, f"symlink-escape marker (backslash) in {label}: {path!r}")
        if any(ch in _BIDI_OVERRIDE_CHARS for ch in path):
            return Denial(DENY_PATH_INVALID, f"symlink-escape marker (bidi-override) in {label}: {path!r}")
        if any(ch in _CONTROL_CHARS for ch in path):
            return Denial(DENY_PATH_INVALID, f"control/NUL byte in {label}: {path!r}")
        if not unicodedata.is_normalized("NFC", path):
            return Denial(DENY_PATH_INVALID, f"non-NFC-normalized path in {label}: {path!r}")
        out.append(path)
    return out


def classify_paths(logical_paths: Any, declared_scopes: Any) -> Union[PathPlan, Denial]:
    """Design §4.2 — PURE syntactic path classification (no filesystem
    access; real resolution is R2/R3).

    `logical_paths` is the grant's SIGNED allowlist of cell-relative
    directory/file prefixes (the containment boundary; "Missing/empty
    allowlist -> deny"). `declared_scopes` is the set of cell-relative
    paths actually requested by the grant's classified effects (e.g. the
    `read`/`write` scope paths from `classify_effects`'s output) that must
    each fall under one `logical_paths` prefix by COMPONENT-AWARE
    containment (never string-prefix — `/a/bc` is NOT under `/a/b`).

    Rejects: absolute host paths, `..` traversal, symlink-escape markers,
    NUL/control bytes, non-NFC Unicode, and casefold/normalization
    collisions between two distinct declared paths (ambiguous target).
    Never raises."""
    try:
        allowlist = _validate_path_syntax(logical_paths, "logical_paths")
        if isinstance(allowlist, Denial):
            return allowlist
        if not allowlist:
            return Denial(DENY_PATH_INVALID, "logical_paths allowlist is empty")
        for prefix in allowlist:
            if ".." in _split_components(prefix):
                return Denial(DENY_PATH_INVALID, f"traversal component in logical_paths: {prefix!r}")

        requested = _validate_path_syntax(declared_scopes, "declared_scopes")
        if isinstance(requested, Denial):
            return requested
        if not requested:
            return Denial(DENY_PATH_INVALID, "declared_scopes is empty")

        allow_components = [_split_components(p) for p in allowlist]

        seen_casefold: dict[tuple[str, ...], str] = {}
        entries: list[tuple[str, tuple[str, ...]]] = []
        for path in requested:
            components = _split_components(path)
            if not components:
                return Denial(DENY_PATH_INVALID, f"empty path after normalization: {path!r}")
            if ".." in components:
                return Denial(DENY_PATH_INVALID, f"traversal component in path: {path!r}")

            casefold_key = tuple(unicodedata.normalize("NFC", c).casefold() for c in components)
            prior = seen_casefold.get(casefold_key)
            if prior is not None and prior != path:
                return Denial(
                    DENY_PATH_INVALID,
                    f"casefold/normalization collision between {prior!r} and {path!r}",
                )
            seen_casefold[casefold_key] = path

            contained = any(
                len(components) >= len(prefix) and components[: len(prefix)] == prefix
                for prefix in allow_components
            )
            if not contained:
                return Denial(DENY_PATH_INVALID, f"path not component-contained under any allowlist prefix: {path!r}")

            entries.append((path, tuple(components)))

        return PathPlan(allowlist=tuple(allowlist), entries=tuple(entries))
    except Exception as exc:  # noqa: BLE001 — total fail-closed
        return Denial(DENY_PATH_INVALID, f"internal path-classification error: {type(exc).__name__}: {exc}")


def _effect_declared_paths(classification: Classification) -> list[str]:
    """Collect the `scope.paths` entries across a `Classification`'s
    effects — the `declared_scopes` input `verify_grant` feeds to
    `classify_paths` (see that function's docstring for the
    logical_paths/declared_scopes mapping)."""
    paths: list[str] = []
    for item in classification.effects:
        scope_paths = item.scope.get("paths")
        if isinstance(scope_paths, list):
            paths.extend(p for p in scope_paths if isinstance(p, str))
    return paths


# --------------------------------------------------------------------------
# Composition (design §5/§8-7) — fixed order, deny-closed, never raises.
# --------------------------------------------------------------------------


def verify_grant(
    grant: Any,
    public_key: bytes,
    now: Optional[datetime],
    current_epoch: Optional[int],
    reservation_set: ReservationInterface,
) -> VerifyResult:
    """Composes every R1 verification + classification pure function in a
    FIXED order: schema -> schema_version -> signature -> freshness ->
    epoch -> effect classification -> path classification -> replay
    reservation. ANY step's failure returns that step's typed `Denial`
    immediately (no reservation is consumed by a grant that fails an
    earlier check). Only an all-pass composition yields an immutable
    `VerifiedGrant` — the sole object later (not-yet-authorized) R2+
    stages accept. NEVER raises: any unexpected exception anywhere in the
    chain is caught here and reported as a `grant-malformed` Denial
    (fail-closed) rather than propagating to the caller."""
    try:
        validated = validate_grant_schema(grant)
        if isinstance(validated, Denial):
            return validated

        version_verdict = verify_schema_version(validated)
        if version_verdict != VERIFY_OK:
            return Denial(version_verdict, "grant_schema_version not in the known closed set")

        signature_verdict = verify_signature(validated, public_key)
        if signature_verdict != VERIFY_OK:
            return Denial(signature_verdict, "grant_digest/Ed25519 signature verification failed")

        freshness_verdict = verify_freshness(validated, now)
        if freshness_verdict != VERIFY_OK:
            return Denial(freshness_verdict, "grant outside its half-open [issued_at, expires_at) window")

        epoch_verdict = verify_epoch(validated, current_epoch)
        if epoch_verdict != VERIFY_OK:
            return Denial(epoch_verdict, "revocation_epoch stale, or epoch source unresolvable")

        classification = classify_effects(validated["effect_set"])
        if isinstance(classification, Denial):
            return classification

        declared_scopes = _effect_declared_paths(classification)
        path_plan = classify_paths(validated["logical_paths"], declared_scopes)
        if isinstance(path_plan, Denial):
            return path_plan

        replay_verdict = reserve_replay(validated["grant_id"], reservation_set)
        if replay_verdict != REPLAY_RESERVED:
            return Denial(DENY_REPLAYED, "grant_id already reserved (replay)")

        return VerifiedGrant(
            grant_id=validated["grant_id"],
            lease_id=validated["lease_id"],
            task_id=validated["task_id"],
            request_id=validated["request_id"],
            base_revision=validated["base_revision"],
            exec_class=validated["exec_class"],
            trusted_repo_id=validated["trusted_repo_id"],
            resource_limits=types.MappingProxyType(dict(validated["resource_limits"])),
            grant_digest=validated["grant_digest"],
            classification=classification,
            path_plan=path_plan,
            raw=types.MappingProxyType(dict(validated)),
        )
    except Exception as exc:  # noqa: BLE001 — total fail-closed, never raise (design §5/§8-7)
        return Denial(DENY_MALFORMED, f"internal verify_grant error: {type(exc).__name__}: {exc}")
