"""CapabilityLease primitive — Foundation C0 (report-only, zero enforcement).

Ships the inert lease building blocks that later enforcement slices (C1+)
will consume as evaluators: dataclasses for Principal/CapabilityLease, a
deterministic canonical-JSON serializer, local HMAC-SHA256 sign/verify, and
monotonic attenuation (child permissions can only shrink relative to a
parent lease).

This module performs NO enforcement and calls NO service — `verify()` only
*reports* a typed verdict, it never blocks or acts. See
`.agents/plans/aqos-foundation-c/C0-IMPLEMENTATION-SPEC.md` for the
authoritative spec this file implements.

Signing key: a machine-local HMAC secret (NOT an API/provider key, NOT an
extracted OAuth credential). Resolved from `AQ_LEASE_SIGNING_KEY` (a path)
or the documented default `/run/secrets/aq-lease-signing-key`. This slice
does not provision that SOPS secret (a later infra slice) — when the path
is absent, `resolve_key()` deterministically falls back to a documented DEV
key and reports `is_dev=True` so a dev signature is never mistaken for a
trust-rooted one. Callers (notably the CLI) MUST surface that fact loudly.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Deterministic, documented DEV-only signing key. Never used to root trust —
# any lease signed with this key is a dev artifact, flagged via is_dev=True.
DEV_SIGNING_KEY: bytes = b"aq-lease-c0-dev-signing-key-DO-NOT-TRUST-IN-PRODUCTION"

DEV_KEY_BANNER: str = "DEV-KEY (unsigned-for-production)"

ENV_KEY_PATH: str = "AQ_LEASE_SIGNING_KEY"
DEFAULT_SECRET_PATH: Path = Path("/run/secrets/aq-lease-signing-key")

VERIFY_OK = "ok"
VERIFY_BAD_SIGNATURE = "bad-signature"
VERIFY_EXPIRED = "expired"
VERIFY_EPOCH_STALE = "epoch-stale"
VERIFY_MALFORMED = "malformed"

PRINCIPAL_KINDS = ("agent", "service", "human", "remote-lane")
ZERO_TRUST_BEHAVIORS = ("none", "strip")

REQUIRED_PRINCIPAL_FIELDS = (
    "principal_id",
    "kind",
    "attestation",
    "trust_tier",
    "session_epoch",
)

REQUIRED_LEASE_FIELDS = (
    "lease_id",
    "version",
    "source",
    "owner",
    "issued_to",
    "issued_at",
    "expires_at",
    "permissions",
    "input_schema",
    "output_schema",
    "trust_tier",
    "zero_trust_behavior",
    "cost_class",
    "parent_lease_id",
    "revocation_epoch",
    "signature",
)

REQUIRED_PERMISSIONS_FIELDS = ("actions", "resources", "constraints")


# --------------------------------------------------------------------------
# Dataclasses
# --------------------------------------------------------------------------


@dataclass
class Principal:
    """The attested identity a lease is issued to (F3 consensus fields)."""

    principal_id: str
    kind: str  # agent | service | human | remote-lane
    attestation: str
    trust_tier: int
    session_epoch: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Principal":
        missing = [f for f in REQUIRED_PRINCIPAL_FIELDS if f not in data]
        if missing:
            raise ValueError(f"Principal missing required fields: {missing}")
        return cls(**{f: data[f] for f in REQUIRED_PRINCIPAL_FIELDS})


@dataclass
class CapabilityLease:
    """Consensus CapabilityLease schema (F3, DESIGN-PACKET §2)."""

    lease_id: str
    version: int
    source: str
    owner: str
    issued_to: str  # principal_id of the Principal this lease was issued to
    issued_at: str  # ISO-8601
    expires_at: str  # ISO-8601
    permissions: dict[str, Any]  # {actions: [...], resources: [...], constraints: {...}}
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    trust_tier: int
    zero_trust_behavior: str  # none | strip
    cost_class: str
    parent_lease_id: Optional[str]
    revocation_epoch: int
    signature: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CapabilityLease":
        missing = [f for f in REQUIRED_LEASE_FIELDS if f not in data]
        if missing:
            raise ValueError(f"CapabilityLease missing required fields: {missing}")
        return cls(**{f: data[f] for f in REQUIRED_LEASE_FIELDS})


LeaseLike = Any  # CapabilityLease | dict[str, Any]


def _as_dict(lease: LeaseLike) -> dict[str, Any]:
    if isinstance(lease, CapabilityLease):
        return lease.to_dict()
    if isinstance(lease, dict):
        return lease
    raise TypeError(f"unsupported lease type: {type(lease)!r}")


# --------------------------------------------------------------------------
# Canonicalization + signing
# --------------------------------------------------------------------------


def canonical_payload(lease: LeaseLike) -> bytes:
    """Deterministic JSON over every lease field EXCEPT `signature`.

    Sorted keys, no whitespace (separators=(',', ':')), UTF-8,
    ensure_ascii=False — this is the exact byte string that gets signed.
    Field order in the source dict never matters (sort_keys=True), so
    re-serializing a re-ordered copy of the same lease produces an
    identical payload and therefore an identical signature.
    """
    data = _as_dict(lease)
    signable = {k: v for k, v in data.items() if k != "signature"}
    return json.dumps(
        signable, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sign(lease: LeaseLike, key: bytes) -> str:
    """HMAC-SHA256(canonical_payload(lease), key) as a hex digest."""
    return hmac.new(key, canonical_payload(lease), hashlib.sha256).hexdigest()


def resolve_key() -> tuple[bytes, bool]:
    """Resolve the local HMAC signing key.

    Order: `AQ_LEASE_SIGNING_KEY` env (path to a key file) → documented
    default `/run/secrets/aq-lease-signing-key`. If neither resolves to a
    readable non-empty file, falls back to the deterministic DEV key.
    Never raises — a missing/unreadable secret path is expected in
    dev/offline/CI and must not crash the caller.

    Returns (key_bytes, is_dev).
    """
    env_path = os.environ.get(ENV_KEY_PATH)
    candidate = Path(env_path) if env_path else DEFAULT_SECRET_PATH
    try:
        if candidate.is_file():
            raw = candidate.read_bytes().strip()
            if raw:
                return raw, False
    except OSError:
        pass
    return DEV_SIGNING_KEY, True


# --------------------------------------------------------------------------
# Time / epoch helpers
# --------------------------------------------------------------------------


def _parse_iso(value: str) -> datetime:
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_expired(lease: LeaseLike, now: Optional[datetime] = None) -> bool:
    data = _as_dict(lease)
    expires_at = _parse_iso(data["expires_at"])
    now = now or datetime.now(timezone.utc)
    return now > expires_at


def epoch_stale(lease: LeaseLike, current_epoch: int) -> bool:
    data = _as_dict(lease)
    return int(data["revocation_epoch"]) < int(current_epoch)


# --------------------------------------------------------------------------
# Verify — report-only, never acts
# --------------------------------------------------------------------------


def _is_malformed(data: dict[str, Any]) -> bool:
    missing = [f for f in REQUIRED_LEASE_FIELDS if f not in data]
    if missing:
        return True
    perms = data.get("permissions")
    if not isinstance(perms, dict):
        return True
    if any(f not in perms for f in REQUIRED_PERMISSIONS_FIELDS):
        return True
    if not isinstance(perms.get("actions"), list) or not isinstance(
        perms.get("resources"), list
    ):
        return True
    if not isinstance(perms.get("constraints"), dict):
        return True
    signature = data.get("signature")
    if not isinstance(signature, str) or not signature:
        return True
    try:
        _parse_iso(data["expires_at"])
    except (TypeError, ValueError):
        return True
    # verify() must be a TOTAL function over well-formed-looking leases —
    # never raise. epoch_stale()/int() on a non-int revocation_epoch (or
    # int(...) on trust_tier/version elsewhere) would otherwise blow up
    # uncaught; catch that here as "malformed" instead. bool is technically
    # an int subclass in Python but is not a valid value for these fields.
    for int_field in ("revocation_epoch", "trust_tier", "version"):
        value = data.get(int_field)
        if not isinstance(value, int) or isinstance(value, bool):
            return True
    return False


def verify(
    lease: LeaseLike, key: bytes, current_epoch: Optional[int] = None
) -> str:
    """Typed, report-only verdict. Check order (first match wins):
    malformed → bad-signature → expired → epoch-stale → ok.
    """
    data = _as_dict(lease)
    if _is_malformed(data):
        return VERIFY_MALFORMED

    expected = sign(data, key)
    actual = data["signature"]
    if not hmac.compare_digest(expected, actual):
        return VERIFY_BAD_SIGNATURE

    if is_expired(data):
        return VERIFY_EXPIRED

    if current_epoch is not None and epoch_stale(data, current_epoch):
        return VERIFY_EPOCH_STALE

    return VERIFY_OK


# --------------------------------------------------------------------------
# Attenuation — monotonic least-privilege, never widens
# --------------------------------------------------------------------------


def _is_strict_numeric(value: Any) -> bool:
    """True for int/float, explicitly excluding bool (bool is an int
    subclass in Python but is not a numeric constraint value here)."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_list_like(value: Any) -> bool:
    return isinstance(value, (list, tuple, set))


def _check_constraints_tighten(
    parent_constraints: dict[str, Any], child_constraints: dict[str, Any]
) -> None:
    """Fail-closed narrowing check, complete over all constraint value
    types (not just numeric).

    Per key present in the parent:
    - missing from the child                     -> RAISE (drops a restriction = widen)
    - both numeric (int/float, bool excluded)     -> child <= parent, else RAISE
    - both list/tuple/set                         -> child must be a subset of parent, else RAISE
    - anything else (str/bool/dict/mismatched types) -> no partial-order
      narrowing is defined for these types, so tightening means "identical
      to parent"; any difference RAISEs.
    A key present only in the child (not in the parent) is a new
    restriction the child is adding on top of the parent — that's always a
    narrowing, so it's accepted without comparison.
    """
    for k, parent_v in parent_constraints.items():
        if k not in child_constraints:
            raise ValueError(
                f"attenuate: delta drops parent constraint {k!r} (would widen)"
            )
        child_v = child_constraints[k]

        if _is_strict_numeric(parent_v) and _is_strict_numeric(child_v):
            if child_v > parent_v:
                raise ValueError(
                    f"attenuate: delta widens numeric constraint {k!r} "
                    f"({child_v} > parent {parent_v})"
                )
            continue

        if _is_list_like(parent_v) and _is_list_like(child_v):
            if not set(child_v) <= set(parent_v):
                raise ValueError(
                    f"attenuate: delta widens list constraint {k!r} — child "
                    f"values not a subset of parent's"
                )
            continue

        if child_v != parent_v:
            raise ValueError(
                f"attenuate: delta widens constraint {k!r} (child {child_v!r} "
                f"!= parent {parent_v!r}; no narrowing semantics defined for "
                f"this value type, so tightening requires an exact match)"
            )


def attenuate(
    parent: LeaseLike, delta: dict[str, Any], key: Optional[bytes] = None
) -> CapabilityLease:
    """Build + sign a child lease attenuated from `parent`.

    `delta` describes the requested child subset (actions/resources/
    constraints/trust_tier/expires_at plus optional identity overrides).
    Any requested widening raises ValueError — permissions can only shrink:
    - actions/resources not present in the parent's sets
    - trust_tier higher than the parent's
    - expires_at later than the parent's
    - a parent constraint dropped, or loosened by the child — "loosened" is
      type-dependent: numeric values must not increase, list/tuple/set
      values must be a subset, and any other type (str/bool/dict/mismatched
      types) must match the parent exactly since no narrowing order is
      defined for it (see `_check_constraints_tighten`)
    """
    parent_data = _as_dict(parent)
    parent_perms = parent_data["permissions"]
    parent_actions = set(parent_perms["actions"])
    parent_resources = set(parent_perms["resources"])
    parent_constraints = dict(parent_perms["constraints"])
    parent_trust_tier = int(parent_data["trust_tier"])
    parent_expires_at = _parse_iso(parent_data["expires_at"])

    requested_actions = set(delta.get("actions", sorted(parent_actions)))
    requested_resources = set(delta.get("resources", sorted(parent_resources)))
    requested_constraints = dict(delta.get("constraints", parent_constraints))
    requested_trust_tier = int(delta.get("trust_tier", parent_trust_tier))
    requested_expires_at_raw = delta.get("expires_at", parent_data["expires_at"])
    requested_expires_at = _parse_iso(requested_expires_at_raw)

    widen_actions = requested_actions - parent_actions
    if widen_actions:
        raise ValueError(
            f"attenuate: delta requests actions not in parent: {sorted(widen_actions)}"
        )
    widen_resources = requested_resources - parent_resources
    if widen_resources:
        raise ValueError(
            f"attenuate: delta requests resources not in parent: {sorted(widen_resources)}"
        )
    if requested_trust_tier > parent_trust_tier:
        raise ValueError(
            f"attenuate: delta trust_tier {requested_trust_tier} exceeds "
            f"parent {parent_trust_tier}"
        )
    if requested_expires_at > parent_expires_at:
        raise ValueError(
            f"attenuate: delta expires_at {requested_expires_at_raw} exceeds "
            f"parent {parent_data['expires_at']}"
        )
    _check_constraints_tighten(parent_constraints, requested_constraints)

    child_actions = sorted(requested_actions & parent_actions)
    child_resources = sorted(requested_resources & parent_resources)

    child = CapabilityLease(
        lease_id=delta.get(
            "lease_id", f"{parent_data['lease_id']}::child::{_now_iso()}"
        ),
        version=int(delta.get("version", 1)),
        source=delta.get("source", parent_data["source"]),
        owner=delta.get("owner", parent_data["owner"]),
        issued_to=delta.get("issued_to", parent_data["issued_to"]),
        issued_at=delta.get("issued_at", _now_iso()),
        expires_at=requested_expires_at_raw,
        permissions={
            "actions": child_actions,
            "resources": child_resources,
            "constraints": requested_constraints,
        },
        input_schema=delta.get("input_schema", parent_data["input_schema"]),
        output_schema=delta.get("output_schema", parent_data["output_schema"]),
        trust_tier=requested_trust_tier,
        zero_trust_behavior=delta.get(
            "zero_trust_behavior", parent_data["zero_trust_behavior"]
        ),
        cost_class=delta.get("cost_class", parent_data["cost_class"]),
        parent_lease_id=parent_data["lease_id"],
        revocation_epoch=int(
            delta.get("revocation_epoch", parent_data["revocation_epoch"])
        ),
        signature="",
    )
    signing_key = key if key is not None else resolve_key()[0]
    child.signature = sign(child, signing_key)
    return child


def lease_from_spec(spec: dict[str, Any], key: bytes) -> CapabilityLease:
    """Build + sign a fresh top-level lease from a spec dict (CLI `new`).

    `spec` must carry every REQUIRED_LEASE_FIELDS entry except `signature`
    (any provided `signature` is ignored and recomputed).
    """
    data = dict(spec)
    data["signature"] = ""
    lease = CapabilityLease.from_dict(data)
    lease.signature = sign(lease, key)
    return lease
