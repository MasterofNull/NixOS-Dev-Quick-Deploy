"""Durable authenticated revocation-epoch primitive — Foundation C, C6-B1 (default-OFF, INERT).

Ships the core fleet-kill-switch primitive C6 is built around: a fail-closed
epoch reader (`read_epoch`), a fail-closed owner-signed bump verifier
(`verify_bump`), and the ONE sanctioned mutation path that applies a verified
bump (`apply_bump`). See `.agents/plans/aqos-foundation-c/C6-FREEZE-20260807.md`
(C6-B1 scope) and `C6-DESIGN-AND-AUTHORIZATION.md` §2 (the design this module
implements) for the authoritative spec.

Nothing in this repository imports this module yet. The confined
`aq-revocation-epoch-authority` service (C6-B2) and the `slot_queue.py`
scheduler fence (C6-B3) are separate, not-yet-built slices that will later
consume it. This slice is a pure library: it opens no socket, holds no
private key, and reads no `/run/secrets`.

FAIL-CLOSED INVARIANTS (the whole point of this module — a fail-open epoch
reader/writer is a fail-open revocation kill-switch):

  - NO bootstrap-to-zero: `read_epoch` on a missing/malformed epoch store
    raises a typed `EpochStoreError` — it NEVER silently returns `0`. A
    present `"0"` (the genesis SSOT already at `config/capability-lease-epoch`)
    is a perfectly valid epoch value; an ABSENT store is an error, not a
    epoch-0 default. Callers (here: `apply_bump`) deny on that error.
  - NO env fallback: every function below takes its epoch/ledger/owner-keys
    location as an EXPLICIT argument. Nothing in this module reads
    `os.environ` to resolve trust-bearing state. (Contrast this
    deliberately with the older, more permissive
    `capability_lease_gate.resolve_current_epoch`, which does fall back
    through an env var and an absent-file default of `0` — that reader
    predates this slice and is NOT reused here.)
  - NO direct epoch-file-write bypass: the epoch file is written by exactly
    one private helper (`_write_epoch_atomic`), reachable ONLY from
    `apply_bump` after verify -> expected-epoch match -> replay-ledger
    check all pass. There is no public function that writes the epoch file
    on its own.
  - NO advisory success: `apply_bump`'s `{"ok": True, ...}` is returned iff
    the epoch file was durably (fsync'd) advanced by exactly +1. Every deny
    path returns `{"ok": False, ...}` and touches no durable state (the
    replay ledger is the one exception documented on `DurableReplayLedger`:
    a key can be durably burned by a failure strictly AFTER the ledger
    record but before/at the epoch write, which is a deliberate
    over-denial on a genuine I/O fault, never a silent success).
  - NO auto-reissue: nothing in this module retries, re-signs, or
    re-submits a bump on the caller's behalf. A denied bump stays denied;
    the owner must construct and sign a fresh request.

Flow (verify -> expected-epoch -> write-ahead journal + two-index reserve
-> atomic +1 -> phase commit): C6d
(`.agents/plans/aqos-foundation-c/C6d-DESIGN-AND-AUTHORIZATION.md`)
replaces the single combined-key `DurableReplayLedger` marker this module
originally recorded BEFORE the epoch mutation — which this docstring used
to warn could permanently wedge a retry (a crash between the marker record
and the durable epoch write left the marker burned forever, denying every
identical retry with no recovery path) — with a write-ahead intent journal
guarded by two INDEPENDENT single-use uniqueness indexes (`resolve()` /
`recover()` below). The epoch CAS (`_write_epoch_atomic`) is still the
SOLE durable commit point, and it still happens under the SAME exclusive
`epoch.lock` as the index reservation and journal writes, so a crash at
ANY point in the transaction leaves on-disk state that `recover()`
deterministically reconciles to exactly-once — never a permanent wedge,
never a fabricated commit. `DurableReplayLedger` is kept below for
`revocation_epoch_transport.build_env_handler` call-site compatibility
only; `apply_bump` no longer consults it for gating (see `apply_bump`'s
own docstring).
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

# --------------------------------------------------------------------------
# Constants — closed `aq.revocation-epoch-bump/1` schema
# (`config/schemas/revocation-epoch-bump.schema.json`, VERIFY-ONLY input,
# not re-created here). Field set below MUST match that schema's
# `required`/`properties` exactly — enforced by the closed-set check in
# `_validate_bump_fields`.
# --------------------------------------------------------------------------

BUMP_SCHEMA = "aq.revocation-epoch-bump/1"
BUMP_SCHEMA_VERSION = "1"

REQUIRED_BUMP_FIELDS = (
    "schema_version",
    "request_id",
    "idempotency_key",
    "issued_at",
    "expires_at",
    "actor_key_id",
    "expected_epoch",
    "reason_code",
    "scope",
    "signature",
)

REASON_CODES = (
    "operator-revoke",
    "policy-rollback",
    "incident",
    "scheduled-rotation",
)

SCOPE_FLEET = "fleet"

# Domain-separated canonical payload (design §2.1: "The Ed25519 signature
# covers a domain-separated canonical payload"). Prevents a signature over
# this schema's canonical bytes from being replayable against any other
# signed-document family in this codebase (leases, scheduler contexts, ...)
# even if a field set happened to collide.
DOMAIN_TAG = b"aq.revocation-epoch-bump/1"

# Bounded validity window for a bump request. Not part of the closed schema
# itself, but a defense-in-depth cap so a signed bump can never be valid
# for an unbounded/very long time (mirrors the context_ttl_cap concept
# elsewhere in Foundation C).
MAX_BUMP_VALIDITY = timedelta(hours=24)
CLOCK_SKEW_TOLERANCE = timedelta(seconds=300)

# --------------------------------------------------------------------------
# Typed epoch-store error vocabulary — `read_epoch` raises exactly one of
# these; it never returns a sentinel int for a bad read.
# --------------------------------------------------------------------------

EPOCH_ERR_MISSING = "epoch-store-missing"
EPOCH_ERR_MALFORMED = "epoch-store-malformed"
EPOCH_ERR_SYMLINK = "epoch-store-symlink"
EPOCH_ERR_NOT_REGULAR = "epoch-store-not-regular"
EPOCH_ERR_IO = "epoch-store-io-error"
EPOCH_AUTHORITY_ERR_SOCKET_UNSET = "epoch-authority-socket-unset"
EPOCH_AUTHORITY_ERR_MALFORMED_RESPONSE = "epoch-authority-malformed-response"
EPOCH_AUTHORITY_ERR_DENIED = "epoch-authority-denied"

_STRICT_NONNEG_INT_RE = re.compile(r"^(0|[1-9][0-9]*)$")
_MAX_EPOCH_FILE_BYTES = 65536


class EpochStoreError(Exception):
    """Typed, fail-closed epoch-store read failure. `reason` is one of the
    `EPOCH_ERR_*` constants above (safe to log); `detail` carries
    non-sensitive diagnostic context only (a path, a class name — never
    key material)."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class EpochAuthorityError(Exception):
    """Typed, fail-closed UDS epoch-resolution failure.

    Unlike the legacy policy-epoch resolver, this error has no sentinel return,
    environment epoch, or file fallback. Callers must convert it to a denial.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


def resolve_current_epoch(socket_path: Any = None, timeout: float = 5.0) -> int:
    """Read the authoritative current epoch over the confined local UDS.

    `AQ_REVOCATION_EPOCH_SOCKET_PATH` supplies the socket path when an explicit
    path is not injected by a hermetic test. An absent/unreachable authority or
    any non-exact response raises `EpochAuthorityError`; this function never
    substitutes an environment epoch, reads the authority file, or returns a
    failure sentinel such as zero.
    """
    candidate = socket_path
    if candidate is None:
        candidate = os.environ.get("AQ_REVOCATION_EPOCH_SOCKET_PATH", "")
    try:
        resolved_path = os.fspath(candidate).strip()
    except (TypeError, ValueError, AttributeError) as exc:
        raise EpochAuthorityError(EPOCH_AUTHORITY_ERR_SOCKET_UNSET, exc.__class__.__name__) from exc
    if not resolved_path:
        raise EpochAuthorityError(EPOCH_AUTHORITY_ERR_SOCKET_UNSET)

    try:
        import revocation_epoch_transport as transport
    except Exception as exc:  # noqa: BLE001 — import failure is authority unavailable, never a fallback
        raise EpochAuthorityError(EPOCH_AUTHORITY_ERR_DENIED, exc.__class__.__name__) from exc

    response = transport.send_request(resolved_path, {"op": "read-epoch"}, timeout=timeout)
    if not isinstance(response, dict):
        raise EpochAuthorityError(EPOCH_AUTHORITY_ERR_MALFORMED_RESPONSE)
    if response.get("ok") is not True:
        reason = response.get("reason")
        detail = response.get("detail")
        raise EpochAuthorityError(
            reason if isinstance(reason, str) and reason else EPOCH_AUTHORITY_ERR_DENIED,
            detail if isinstance(detail, str) else "",
        )
    epoch = response.get("epoch")
    if set(response) != {"ok", "epoch"} or isinstance(epoch, bool) or not isinstance(epoch, int) or epoch < 0:
        raise EpochAuthorityError(EPOCH_AUTHORITY_ERR_MALFORMED_RESPONSE)
    return epoch


def read_epoch(epoch_path: Any) -> int:
    """Read the durable epoch integer from `epoch_path`, fail-closed.

    A MISSING, non-regular, symlinked, oversized, non-UTF-8, or malformed
    (not a single strict non-negative decimal integer — no leading zeros,
    no sign, no whitespace inside the digits) epoch store raises a typed
    `EpochStoreError`; it NEVER returns `0` as a silent default. A present
    `"0"` is the valid genesis epoch and returns `0` normally — that is the
    one and only path that yields `0`.
    """
    path = Path(epoch_path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path), flags)
    except FileNotFoundError:
        raise EpochStoreError(EPOCH_ERR_MISSING, str(path)) from None
    except NotADirectoryError:
        raise EpochStoreError(EPOCH_ERR_MISSING, str(path)) from None
    except OSError as exc:
        if getattr(exc, "errno", None) == errno.ELOOP:
            raise EpochStoreError(EPOCH_ERR_SYMLINK, str(path)) from None
        raise EpochStoreError(EPOCH_ERR_IO, f"{path}: {exc.__class__.__name__}") from None

    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise EpochStoreError(EPOCH_ERR_NOT_REGULAR, str(path))
        raw = os.read(fd, _MAX_EPOCH_FILE_BYTES)
        if len(raw) >= _MAX_EPOCH_FILE_BYTES:
            # Refuse to guess at a truncated read of an oversized/malformed
            # store rather than silently parsing a partial value.
            raise EpochStoreError(EPOCH_ERR_MALFORMED, "epoch store exceeds max size")
    except EpochStoreError:
        raise
    except OSError as exc:
        raise EpochStoreError(EPOCH_ERR_IO, f"{path}: {exc.__class__.__name__}") from None
    finally:
        os.close(fd)

    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        raise EpochStoreError(EPOCH_ERR_MALFORMED, "epoch store not valid utf-8") from None

    if not text or not _STRICT_NONNEG_INT_RE.match(text):
        raise EpochStoreError(EPOCH_ERR_MALFORMED, f"content={text!r}")

    return int(text)


# --------------------------------------------------------------------------
# Canonicalization + offline-signing helper (test/owner-tool use only — the
# CLI never calls `sign_bump`; it has no private key)
# --------------------------------------------------------------------------


def canonical_bump_payload(bump_doc: Mapping[str, Any]) -> bytes:
    """Domain-separated deterministic JSON over every field of `bump_doc`
    EXCEPT `signature` — the exact byte string that is signed/verified.
    Sorted keys, no whitespace, UTF-8. Field order in the source mapping
    never matters."""
    data = dict(bump_doc)
    data.pop("signature", None)
    body = json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return DOMAIN_TAG + b"\x00" + body


def sign_bump(bump_doc: Mapping[str, Any], private_key_bytes: bytes) -> str:
    """Ed25519-sign `canonical_bump_payload(bump_doc)`, return a hex
    signature. FOR OFFLINE OWNER-SIGNING TOOLING AND TEST FIXTURES ONLY.
    `aq-epoch-bump` (the CLI shipped alongside this module) never calls
    this function and never holds owner private-key material — the owner
    signs the printed canonical bytes with their own external tooling."""
    private_key = Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    payload = canonical_bump_payload(bump_doc)
    return private_key.sign(payload).hex()


# --------------------------------------------------------------------------
# Verify — total function, never raises, never mutates anything
# --------------------------------------------------------------------------

BUMP_OK = "ok"

DENY_MALFORMED = "bump-malformed"
DENY_SCHEMA_VERSION = "schema-version-mismatch"
DENY_REASON_CODE = "reason-code-invalid"
DENY_SCOPE = "scope-not-fleet"
DENY_EXPIRED = "bump-expired"
DENY_NOT_YET_VALID = "bump-not-yet-valid"
DENY_MALFORMED_KEYS = "owner-keys-malformed"
DENY_UNKNOWN_KEY = "unknown-key-id"
DENY_KEY_NOT_ACTIVE = "key-not-active"
DENY_BAD_SIGNATURE = "bad-signature"
DENY_EPOCH_MISMATCH = "expected-epoch-mismatch"
DENY_REPLAY = "replay-request"
DENY_LEDGER_UNAVAILABLE = "ledger-unavailable"
DENY_LOCK_UNAVAILABLE = "epoch-lock-unavailable"
DENY_EPOCH_WRITE_FAILED = "epoch-write-failed"
DENY_INTERNAL = "internal-error"

# --------------------------------------------------------------------------
# C6d additions (`.agents/plans/aqos-foundation-c/C6d-DESIGN-AND-AUTHORIZATION.md`)
# -- the write-ahead journal + two-index deterministic-recovery primitive.
# `DENY_REPLAY` above is RETIRED from the `apply_bump` live path (kept
# defined for import compatibility only): a replay of an already-COMMITTED
# transaction is no longer denied -- `resolve()`'s `committed` row returns
# the ORIGINAL receipt idempotently (design §3.2), and an uncommitted-intent
# retry (the old permanently-wedged W1 defect) is never `DENY_REPLAY` either
# -- it is one of the two new typed outcomes below.
# --------------------------------------------------------------------------
DENY_RETRY = "bump-retry-required"
DENY_IDENTITY_CONFLICT = "identity-conflict"
DENY_QUARANTINED = "quarantined"
DENY_ABORTED_TERMINAL = "bump-aborted-terminal"


@dataclass(frozen=True)
class BumpVerdict:
    """Typed, report-only outcome of `verify_bump` — never raises, never
    acts. `ok=True` iff `reason == BUMP_OK`; every other `reason` is one of
    the `DENY_*` constants above and is safe to log."""

    ok: bool
    reason: str
    detail: str = ""


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str) -> datetime:
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _validate_bump_fields(data: Mapping[str, Any]) -> Optional[str]:
    """Closed-schema structural/type validation. Returns a `DENY_*` reason
    or `None` if well-formed. Field SET must match `REQUIRED_BUMP_FIELDS`
    exactly (mirrors the schema's `additionalProperties: false` + full
    `required` list — every property is required, none are optional)."""
    if set(data.keys()) != set(REQUIRED_BUMP_FIELDS):
        return DENY_MALFORMED

    if data.get("schema_version") != BUMP_SCHEMA_VERSION:
        return DENY_SCHEMA_VERSION

    for field in ("request_id", "idempotency_key", "actor_key_id", "signature"):
        value = data.get(field)
        if not isinstance(value, str) or not value:
            return DENY_MALFORMED

    expected_epoch = data.get("expected_epoch")
    if (
        not isinstance(expected_epoch, int)
        or isinstance(expected_epoch, bool)
        or expected_epoch < 0
    ):
        return DENY_MALFORMED

    if data.get("reason_code") not in REASON_CODES:
        return DENY_REASON_CODE

    if data.get("scope") != SCOPE_FLEET:
        return DENY_SCOPE

    for field in ("issued_at", "expires_at"):
        value = data.get(field)
        if not isinstance(value, str):
            return DENY_MALFORMED
        try:
            _parse_iso(value)
        except (TypeError, ValueError):
            return DENY_MALFORMED

    return None


def _check_freshness(data: Mapping[str, Any], now: Optional[datetime]) -> Optional[str]:
    issued_at = _parse_iso(data["issued_at"])
    expires_at = _parse_iso(data["expires_at"])
    if expires_at <= issued_at or (expires_at - issued_at) > MAX_BUMP_VALIDITY:
        return DENY_MALFORMED

    moment = now or datetime.now(timezone.utc)
    if moment > expires_at:
        return DENY_EXPIRED
    if moment < issued_at - CLOCK_SKEW_TOLERANCE:
        return DENY_NOT_YET_VALID
    return None


def _verify_signature(data: Mapping[str, Any], owner_keys_json_dict: Any) -> Optional[str]:
    if not isinstance(owner_keys_json_dict, Mapping):
        return DENY_MALFORMED_KEYS
    keys = owner_keys_json_dict.get("keys")
    if not isinstance(keys, list) or not keys:
        return DENY_MALFORMED_KEYS

    key_id = data.get("actor_key_id")
    matched: Optional[Mapping[str, Any]] = None
    for entry in keys:
        if isinstance(entry, Mapping) and entry.get("key_id") == key_id:
            matched = entry
            break
    if matched is None:
        return DENY_UNKNOWN_KEY

    # Status re-checked on EVERY call — no caching of a prior active
    # result (mirrors capability_lease.verify_authoritative).
    if matched.get("status") != "active":
        return DENY_KEY_NOT_ACTIVE

    pubkey_hex = matched.get("ed25519_public_key")
    if not isinstance(pubkey_hex, str):
        return DENY_MALFORMED_KEYS
    try:
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pubkey_hex))
    except (ValueError, TypeError):
        return DENY_MALFORMED_KEYS

    sig_hex = data.get("signature")
    try:
        signature_bytes = bytes.fromhex(sig_hex)
    except (ValueError, TypeError):
        return DENY_BAD_SIGNATURE

    try:
        public_key.verify(signature_bytes, canonical_bump_payload(data))
    except Exception:
        return DENY_BAD_SIGNATURE

    return None


def verify_bump(
    bump_doc: Any, owner_keys_json_dict: Any, now: Optional[datetime] = None
) -> BumpVerdict:
    """Deny-closed, total verify: schema -> freshness -> signature. Checks
    (first match wins): malformed -> schema-version -> reason-code -> scope
    -> malformed timestamps -> expired/not-yet-valid -> owner-key lookup
    (unknown/not-active) -> bad-signature -> ok. Never raises; never
    mutates anything; does NOT check `expected_epoch` against durable
    state (that is `apply_bump`'s job, since this function has no
    `epoch_path`)."""
    try:
        if not isinstance(bump_doc, Mapping):
            return BumpVerdict(False, DENY_MALFORMED, "bump not a mapping")
        data = dict(bump_doc)

        reason = _validate_bump_fields(data)
        if reason is not None:
            return BumpVerdict(False, reason)

        reason = _check_freshness(data, now)
        if reason is not None:
            return BumpVerdict(False, reason)

        reason = _verify_signature(data, owner_keys_json_dict)
        if reason is not None:
            return BumpVerdict(False, reason)

        return BumpVerdict(True, BUMP_OK)
    except Exception as exc:  # noqa: BLE001 — total function, never raises into the caller
        return BumpVerdict(False, DENY_MALFORMED, f"unhandled:{exc.__class__.__name__}")


# --------------------------------------------------------------------------
# Durable single-use replay ledger — keyed on {request_id, idempotency_key}.
# Mirrors `scheduler_context_issuer.DurableSingleUseLedger`'s O_EXCL +
# fsync(file)+fsync(dir) atomicity/durability pattern; reimplemented here
# (not imported) to keep this module's dependency surface self-contained —
# the same "minimal confined-service bundle" discipline
# `lease_signing_authority.py` documents (WR-3 lesson).
# --------------------------------------------------------------------------


class DurableReplayLedger:
    """One empty(-ish) marker file per consumed `(request_id,
    idempotency_key)` pair, named `sha256(f"{request_id}\\x00{idempotency_key}")`
    under `ledger_dir`. `check_and_record` is `os.open(path, O_CREAT |
    O_EXCL, ...)` — a single atomic kernel syscall: exactly one of two
    racing callers for the identical key observes "I created it" (True),
    the other observes `FileExistsError` (False). This holds across
    threads, processes, and — because the state is the filesystem, not
    process memory — across a process restart: a NEW instance pointed at
    the SAME `ledger_dir` sees every previously recorded key as already
    used. The marker's bytes and directory entry are both fsync'd before a
    `True` return.

    FAIL-CLOSED: `EEXIST` (already used) is the only condition returning
    `False`. Any OTHER `OSError` (permission denied, disk full, dir
    missing/unwritable) propagates — the caller (`apply_bump`) turns that
    into `DENY_LEDGER_UNAVAILABLE`, never a silent "go ahead"."""

    def __init__(self, ledger_dir: str) -> None:
        self._dir = ledger_dir
        os.makedirs(self._dir, mode=0o700, exist_ok=True)
        self._recorded = 0
        self._replays = 0

    def _key_path(self, key: tuple[str, str]) -> str:
        request_id, idempotency_key = key
        digest = hashlib.sha256(
            f"{request_id}\x00{idempotency_key}".encode("utf-8")
        ).hexdigest()
        return os.path.join(self._dir, digest)

    def check_and_record(self, key: tuple[str, str]) -> bool:
        path = self._key_path(key)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            self._replays += 1
            return False
        try:
            payload = json.dumps(
                {
                    "request_id": key[0],
                    "idempotency_key": key[1],
                    "recorded_at": _iso(datetime.now(timezone.utc)),
                },
                sort_keys=True,
            ).encode("utf-8")
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        dir_fd = os.open(self._dir, os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
        self._recorded += 1
        return True

    def stats(self) -> dict[str, int]:
        """Best-effort in-process counters for dashboard/O2 wiring — NOT
        the durable audit trail (the marker files are); resets to zero on
        restart even though every deny/allow decision remains durable and
        correct."""
        return {"recorded": self._recorded, "replays": self._replays}


# --------------------------------------------------------------------------
# The sole mutation path — atomic epoch write + exclusive lock helpers.
# Both are private (module-internal); the ONLY way to reach
# `_write_epoch_atomic` is through `apply_bump`.
# --------------------------------------------------------------------------


def _acquire_epoch_lock(epoch_path: Path) -> int:
    lock_path = epoch_path.parent / (epoch_path.name + ".lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(lock_path), flags, 0o600)
    fcntl.flock(fd, fcntl.LOCK_EX)
    return fd


def _release_epoch_lock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _write_epoch_atomic(epoch_path: Path, new_epoch: int) -> None:
    """Same-directory temp file, fsync, atomic `os.replace`, fsync the
    directory entry. The ONLY function in this module that writes the
    epoch file's content."""
    directory = epoch_path.parent
    fd, tmp_path = tempfile.mkstemp(
        dir=str(directory), prefix=f".{epoch_path.name}.", suffix=".tmp"
    )
    try:
        os.write(fd, f"{new_epoch}\n".encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp_path, 0o640)
    os.replace(tmp_path, str(epoch_path))
    dir_fd = os.open(str(directory), os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _append_audit_receipt(epoch_path: Path, receipt: Mapping[str, Any]) -> None:
    """Append-only, bounded (fixed-field) JSONL audit line next to the
    epoch file. Best-effort observability, NOT the authority for whether a
    bump happened (the epoch file + replay ledger are); a failure here
    marks the receipt `audit_pending` but never reverses an already
    durable epoch advance (mirrors design §2.2's `committed_audit_pending`
    semantics — a bump that happened is never re-described as one that
    did not)."""
    audit_path = epoch_path.parent / (epoch_path.name + ".audit.jsonl")
    line = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(str(audit_path), flags, 0o640)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


# --------------------------------------------------------------------------
# C6d journal + two-index primitive (design §2). Three StateDirectories,
# siblings of `epoch_path`: `journal/<entry_id>` (the write-ahead intent ->
# committed/aborted record), `by-request-id/<H(request_id)>` and
# `by-idempotency-key/<H(idempotency_key)>` (two INDEPENDENT single-use
# uniqueness indexes, each storing the `entry_id` they point at). All
# reachable only under `epoch.lock` (§3.1's serialization invariant), so
# every helper below assumes the caller already holds it.
# --------------------------------------------------------------------------


def _sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _entry_id(request_id: str, idempotency_key: str) -> str:
    """`sha256(request_id \\x00 idempotency_key)` -- a FILENAME only; the
    two independent indexes below, not this composite, are what enforce
    uniqueness (design §2.1)."""
    return hashlib.sha256(f"{request_id}\x00{idempotency_key}".encode("utf-8")).hexdigest()


def _derive_state_dirs(epoch_path: Path) -> tuple[Path, Path, Path]:
    """`journal/`, `by-request-id/`, `by-idempotency-key/` -- siblings of
    `epoch_path`. The confined Nix unit also declares these via
    `systemd.tmpfiles.rules` (0700, authority-owned) ahead of first start;
    creating them here too (idempotent `exist_ok=True`) means an offline
    caller (tests, a future owner CLI) never depends on unit-start
    ordering, mirroring `DurableReplayLedger.__init__`'s own eager
    `os.makedirs`."""
    parent = epoch_path.parent
    journal_dir = parent / "journal"
    by_request_id_dir = parent / "by-request-id"
    by_idempotency_key_dir = parent / "by-idempotency-key"
    for directory in (journal_dir, by_request_id_dir, by_idempotency_key_dir):
        os.makedirs(str(directory), mode=0o700, exist_ok=True)
    return journal_dir, by_request_id_dir, by_idempotency_key_dir


def _fsync_dir(directory: Path) -> None:
    dir_fd = os.open(str(directory), os.O_DIRECTORY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def _listdir_safe(directory: Path) -> list[str]:
    try:
        return os.listdir(str(directory))
    except (FileNotFoundError, NotADirectoryError):
        return []


def _load_json_or_none(path: Path) -> tuple[bool, Optional[dict[str, Any]]]:
    """`(exists, data)`. `exists=False` iff the path is genuinely absent.
    `exists=True, data=None` covers a present-but-unreadable/corrupt file
    (torn state) -- the caller decides how to treat that (never silently
    treated as absent, never silently treated as valid)."""
    try:
        with open(str(path), "rb") as fh:
            raw = fh.read()
    except FileNotFoundError:
        return False, None
    except OSError:
        return True, None
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return True, None
    return True, (decoded if isinstance(decoded, dict) else None)


def _create_exclusive_json(path: Path, data: Mapping[str, Any], mode: int) -> bool:
    """`O_CREAT|O_EXCL|O_NOFOLLOW` create + `fsync(file)`+`fsync(dir)`. True
    iff THIS call created the file; False on `EEXIST`. Any OTHER `OSError`
    propagates -- fail-closed, mirrors `DurableReplayLedger.check_and_record`."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path), flags, mode)
    except FileExistsError:
        return False
    try:
        payload = json.dumps(dict(data), sort_keys=True, separators=(",", ":")).encode("utf-8")
        os.write(fd, payload)
        os.fsync(fd)
    finally:
        os.close(fd)
    _fsync_dir(path.parent)
    return True


def _atomic_rewrite_journal_entry(path: Path, data: Mapping[str, Any]) -> None:
    """Same-directory temp file, fsync, atomic `os.replace`, fsync the
    directory entry -- the in-place `phase` rewrite primitive (fresh
    `intent`->`committed`/`aborted`, and the deterministic `aborted`->
    `intent` tombstone reuse). Mirrors `_write_epoch_atomic` exactly."""
    directory = path.parent
    fd, tmp_path = tempfile.mkstemp(dir=str(directory), prefix=f".{path.name}.", suffix=".tmp")
    try:
        os.write(fd, json.dumps(dict(data), sort_keys=True, separators=(",", ":")).encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp_path, 0o640)
    os.replace(tmp_path, str(path))
    _fsync_dir(directory)


def _release_index_if_points_to(path: Path, entry_id: str) -> None:
    """Unlink `path` (+ `fsync(dir)`) ONLY if it still exists and its
    stored `entry_id` matches -- never release an index pointing at a
    DIFFERENT (legitimate) entry. A missing or unreadable/corrupt index is
    left untouched (never guessed at); idempotent no-op if already gone."""
    exists, data = _load_json_or_none(path)
    if not exists:
        return
    if not isinstance(data, Mapping) or data.get("entry_id") != entry_id:
        return
    try:
        os.unlink(str(path))
    except FileNotFoundError:
        return
    _fsync_dir(path.parent)


def _release_indexes_for(
    pair: tuple[str, str],
    by_request_id_dir: Path,
    by_idempotency_key_dir: Path,
    entry_id: str,
) -> None:
    request_id, idempotency_key = pair
    _release_index_if_points_to(by_request_id_dir / _sha256_hex(request_id), entry_id)
    _release_index_if_points_to(by_idempotency_key_dir / _sha256_hex(idempotency_key), entry_id)


def _receipt_ok_from_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    receipt = {
        "old_epoch": entry.get("old_epoch"),
        "new_epoch": entry.get("new_epoch"),
        "actor_key_id": entry.get("actor_key_id"),
        "reason_code": entry.get("reason_code"),
        "request_id": entry.get("request_id"),
        "idempotency_key": entry.get("idempotency_key"),
        "committed_at": entry.get("committed_at"),
        "audit_pending": bool(entry.get("audit_pending", False)),
    }
    return {"ok": True, "reason": BUMP_OK, "detail": "", "receipt": receipt}


def _reconcile_audit_pending(
    entry: Mapping[str, Any], journal_path: Path, epoch_path: Path
) -> dict[str, Any]:
    """Design §5 vector h -- a `committed` entry whose durably-persisted
    `audit_pending` is `True` never got its best-effort audit line
    written (a crash, or a live append the caller never retried). Retry
    the append now; on success, durably clear `audit_pending` in the
    journal entry via the existing temp+fsync+rename atomic primitive --
    the "audit reconciled" outcome the design names for this vector.
    Fail-closed: if the retry itself fails, the entry (and its persisted
    `audit_pending`) is left untouched for the NEXT reconciliation pass --
    never silently cleared without a confirmed append. Never raises
    (mirrors the total-function contract of its callers)."""
    receipt_for_audit = dict(_receipt_ok_from_entry(entry)["receipt"])
    receipt_for_audit["audit_pending"] = False
    try:
        _append_audit_receipt(epoch_path, receipt_for_audit)
    except OSError:
        return dict(entry)
    reconciled = dict(entry)
    reconciled["audit_pending"] = False
    _atomic_rewrite_journal_entry(journal_path, reconciled)
    return reconciled


def resolve(
    entry_id: str,
    epoch_path: Path,
    journal_dir: Path,
    by_request_id_dir: Path,
    by_idempotency_key_dir: Path,
    presented: Optional[tuple[str, str]] = None,
) -> dict[str, Any]:
    """Design §3.2 -- the deterministic branch, and the unit of `recover()`.
    A TOTAL function: every `{journal-presence, phase, current, presented}`
    input maps to exactly one typed outcome; NEVER raises (preserves
    `apply_bump`'s never-raise contract). `recover()` calls this with
    `presented=None` (the entry is authoritative for its own identity, and
    the journal-absent identity-gate row is unreachable from `recover()` --
    it iterates journal entries that exist). The LIVE `apply_bump` path
    calls this with `presented=(request_id, idempotency_key)` after an
    index `EEXIST` (§3.1 step 2)."""
    try:
        journal_path = journal_dir / entry_id

        exists, entry = _load_json_or_none(journal_path)

        if not exists:
            # Identity gate, row 1 -- orphan reservation, intent never
            # durable (live view of crash vectors a/b/c). `recover()` never
            # reaches this row (its own orphan-index sweep, §3.3 step 1,
            # handles the journal-absent case directly).
            if presented is not None:
                _release_indexes_for(presented, by_request_id_dir, by_idempotency_key_dir, entry_id)
            return _bump_deny(DENY_RETRY, "journal-absent-orphan-index-released")

        if entry is None:
            # Present but unreadable/corrupt -- torn state, never fabricate.
            return _bump_deny(DENY_QUARANTINED, "journal-entry-unreadable")

        stored_pair = (entry.get("request_id"), entry.get("idempotency_key"))

        if presented is not None and stored_pair != tuple(presented):
            # Identity gate, row 2 -- cross-identity reuse. Never the
            # existing receipt, never mutate the epoch, never release the
            # legitimate entry's indexes, never bump.
            return _bump_deny(DENY_IDENTITY_CONFLICT, "presented-identity-does-not-match-stored-entry")

        phase = entry.get("phase")

        if phase == "committed":
            # (h) or a legitimate idempotent replay of an already-durable
            # success -- exactly-once: return the SAME reconstructed
            # receipt, never a fresh mutation. Design §5 vector h: a
            # persisted `audit_pending=True` means the best-effort audit
            # append never landed for this transaction -- retry it now
            # and durably clear the flag on success (fail-closed on
            # retry failure; see `_reconcile_audit_pending`).
            if entry.get("audit_pending", False):
                entry = _reconcile_audit_pending(entry, journal_path, epoch_path)
            return _receipt_ok_from_entry(entry)

        if phase == "intent":
            try:
                current = read_epoch(epoch_path)
            except EpochStoreError as exc:
                return _bump_deny(exc.reason, exc.detail)
            old_epoch = entry.get("old_epoch")
            new_epoch = entry.get("new_epoch")
            if current == new_epoch:
                # (g) -- CAS committed, phase-commit rewrite crashed.
                # Finalize. The audit append never ran for this
                # transaction either (the crash predates it) -- persist
                # `audit_pending=True` on the same finalize write, then
                # attempt reconciliation immediately (same fail-closed
                # semantics as the already-`committed` branch above).
                committed_entry = dict(entry)
                committed_entry["phase"] = "committed"
                committed_entry["committed_at"] = _iso(datetime.now(timezone.utc))
                committed_entry["audit_pending"] = True
                _atomic_rewrite_journal_entry(journal_path, committed_entry)
                committed_entry = _reconcile_audit_pending(committed_entry, journal_path, epoch_path)
                return _receipt_ok_from_entry(committed_entry)
            if current == old_epoch:
                # (d)/W1 -- CAS never happened. Abort FIRST (durable), then
                # release both indexes. Never `DENY_REPLAY` -- a typed
                # retryable deny; the identical retry re-reserves fresh and
                # (apply_bump step 3) rewrites this tombstone back to intent.
                aborted_entry = dict(entry)
                aborted_entry["phase"] = "aborted"
                _atomic_rewrite_journal_entry(journal_path, aborted_entry)
                _release_indexes_for(stored_pair, by_request_id_dir, by_idempotency_key_dir, entry_id)
                return _bump_deny(DENY_RETRY, "intent-aborted-retry-will-bump")
            # current NOT in {old, new} -- an unrelated bump advanced the
            # epoch while this intent was unresolved. Never fabricate.
            return _bump_deny(
                DENY_QUARANTINED,
                f"torn-intent old_epoch={old_epoch} new_epoch={new_epoch} current={current}",
            )

        if phase == "aborted":
            # Terminal tombstone. `recover()` (presented=None) leaves it
            # alone -- informational only, never an operator alarm. A live
            # call only reaches this row via a stale dangling index that
            # still points at an already-aborted entry (vector i not yet
            # reconciled) -- release the dangling pointer and hand back a
            # retryable deny so the identical retry re-reserves fresh.
            if presented is not None:
                _release_indexes_for(stored_pair, by_request_id_dir, by_idempotency_key_dir, entry_id)
                return _bump_deny(DENY_RETRY, "aborted-tombstone-dangling-index-released")
            return _bump_deny(DENY_ABORTED_TERMINAL, "aborted-tombstone-terminal-noop")

        # Unknown/malformed `phase` value -- torn state, never fabricated.
        return _bump_deny(DENY_QUARANTINED, f"unknown-phase:{phase!r}")
    except Exception as exc:  # noqa: BLE001 -- total function, never raises into the caller
        return _bump_deny(DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")


def recover(epoch_path: Any) -> dict[str, Any]:
    """Design §3.3 -- the index<->journal bipartite reconciliation pass.
    Runs to COMPLETION under `epoch.lock`, BEFORE the authority transport
    binds/listens/accepts (§3.4; see `revocation_epoch_transport.__main__`).
    Never raises; returns a summary dict for logging/observability. An
    entry that cannot be resolved cleanly is counted under
    `resolved_quarantined`, never silently dropped or treated as a no-op.

    Three steps, in order (each is deterministic and needs no epoch read
    of its own except where `resolve()`'s phase table requires one):
      1. Orphan-index sweep -- an index whose target journal is ABSENT is
         proof the transaction never reached a durable intent (the epoch
         CAS can only follow a durable intent) -- release it.
      2. Journal resolution -- `resolve(entry_id)` per existing journal
         entry: finalizes a committed-but-unphased intent, aborts+releases
         an uncommitted intent, reconstructs a committed receipt, leaves a
         terminal `aborted` alone, or quarantines a torn `{epoch, phase}`.
      3. Dangling-index-after-abort cleanup -- an index that still points
         at a now-terminal `aborted` journal entry is released (vector i).
    """
    epoch_path_p = Path(epoch_path)
    summary: dict[str, Any] = {
        "orphan_indexes_released": 0,
        "resolved_committed": 0,
        "resolved_aborted_and_released": 0,
        "resolved_quarantined": 0,
        "dangling_indexes_after_abort_released": 0,
        "legacy_ledger_markers_detected": 0,
        "error": None,
    }
    try:
        lock_fd = _acquire_epoch_lock(epoch_path_p)
    except OSError as exc:
        summary["error"] = f"lock-unavailable:{exc.__class__.__name__}"
        return summary
    try:
        journal_dir, by_request_id_dir, by_idempotency_key_dir = _derive_state_dirs(epoch_path_p)

        # Step 1 -- orphan-index sweep (journal-absent).
        for index_dir in (by_request_id_dir, by_idempotency_key_dir):
            for name in sorted(_listdir_safe(index_dir)):
                index_path = index_dir / name
                _, data = _load_json_or_none(index_path)
                pointed_entry_id = data.get("entry_id") if isinstance(data, Mapping) else None
                if not isinstance(pointed_entry_id, str) or not pointed_entry_id:
                    continue
                if not (journal_dir / pointed_entry_id).exists():
                    try:
                        os.unlink(str(index_path))
                        _fsync_dir(index_dir)
                        summary["orphan_indexes_released"] += 1
                    except FileNotFoundError:
                        pass

        # Step 2 -- journal resolution, per existing entry.
        for entry_id in sorted(_listdir_safe(journal_dir)):
            outcome = resolve(
                entry_id, epoch_path_p, journal_dir, by_request_id_dir, by_idempotency_key_dir,
                presented=None,
            )
            reason = outcome.get("reason")
            if outcome.get("ok"):
                summary["resolved_committed"] += 1
            elif reason == DENY_RETRY:
                summary["resolved_aborted_and_released"] += 1
            elif reason == DENY_QUARANTINED:
                summary["resolved_quarantined"] += 1
            # DENY_ABORTED_TERMINAL (already-terminal tombstone, no action
            # needed) and any typed epoch-store-* read failure are neither
            # a commit nor a fresh abort -- left uncounted, never fabricated
            # into either bucket.

        # Step 3 -- dangling-index-after-abort cleanup (vector i).
        for index_dir in (by_request_id_dir, by_idempotency_key_dir):
            for name in sorted(_listdir_safe(index_dir)):
                index_path = index_dir / name
                _, data = _load_json_or_none(index_path)
                pointed_entry_id = data.get("entry_id") if isinstance(data, Mapping) else None
                if not isinstance(pointed_entry_id, str) or not pointed_entry_id:
                    continue
                _, entry = _load_json_or_none(journal_dir / pointed_entry_id)
                if isinstance(entry, Mapping) and entry.get("phase") == "aborted":
                    try:
                        os.unlink(str(index_path))
                        _fsync_dir(index_dir)
                        summary["dangling_indexes_after_abort_released"] += 1
                    except FileNotFoundError:
                        pass

        # Legacy single-index `DurableReplayLedger` marker detection --
        # minimal detect-and-log ONLY, no import path (design §2.3/§7: a
        # non-empty legacy `ledger/` is a consumed-but-unrecoverable key
        # with no journal entry -- operator-visible, never a silent bump).
        legacy_ledger_dir = epoch_path_p.parent / "ledger"
        legacy_markers = _listdir_safe(legacy_ledger_dir)
        if legacy_markers:
            summary["legacy_ledger_markers_detected"] = len(legacy_markers)
            print(
                f"[revocation_epoch.recover] WARN: {len(legacy_markers)} legacy single-index "
                f"replay-ledger marker(s) found under {legacy_ledger_dir} -- each is a "
                f"consumed-but-unrecoverable key with no journal entry (quarantined by design, "
                f"never imported/migrated -- see C6d-DESIGN-AND-AUTHORIZATION.md §2.3/§7)",
                file=sys.stderr,
                flush=True,
            )

        return summary
    finally:
        _release_epoch_lock(lock_fd)


def _bump_deny(reason: str, detail: str = "") -> dict[str, Any]:
    return {"ok": False, "reason": reason, "detail": detail, "receipt": None}


def apply_bump(
    bump_doc: Any,
    epoch_path: Any,
    ledger: "DurableReplayLedger",
    owner_keys_json_dict: Any,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Verify -> expected-epoch match -> write-ahead journal + two-index
    reservation -> atomic +1 -> phase commit -> audit receipt. Returns
    `{"ok": True, "reason": BUMP_OK, "detail": "", "receipt": {...}}` on
    success, or `{"ok": False, "reason": DENY_*, "detail": ..., "receipt":
    None}` on ANY deny. Total function — never raises.

    C6d (`.agents/plans/aqos-foundation-c/C6d-DESIGN-AND-AUTHORIZATION.md`
    §3.1) replaces the OLD "burn a single combined-key ledger marker, then
    separately advance the epoch" split — which the module used to admit
    could permanently wedge a retry (a crash between the marker record and
    the durable epoch write left the marker burned but the epoch
    un-advanced, and the identical retry then hit the marker and denied
    forever) — with a write-ahead intent journal guarded by two
    INDEPENDENT single-use uniqueness indexes, finalized before any
    request is served (see `recover()` / the transport's recover-before-
    listen barrier). `ledger` is accepted but NOT consulted for gating —
    it is kept ONLY for call-site signature compatibility with
    `revocation_epoch_transport.build_env_handler`; re-introducing a
    `ledger.check_and_record` gate here would reintroduce the exact
    wedging defect this slice closes.

    Order under one exclusive `epoch.lock` hold: `verify_bump` (no state
    touched) -> `read_epoch` (typed unavailable deny, never `0`) ->
    expected-epoch compare (stale-bump deny, stateless, no index/journal
    touched) -> reserve both uniqueness indexes (an `EEXIST` hands off to
    `resolve()` — replay/recovery/conflict, see design §3.1 step 2) ->
    establish the write-ahead intent (fresh create, or the deterministic
    `aborted`->`intent` tombstone reuse) -> the epoch CAS (`_write_epoch_
    atomic` — the SOLE durable commit point) -> phase-commit rewrite (the
    committed journal entry IS the durable receipt) -> best-effort audit
    projection."""
    try:
        verdict = verify_bump(bump_doc, owner_keys_json_dict, now=now)
        if not verdict.ok:
            return _bump_deny(verdict.reason, verdict.detail)

        data = dict(bump_doc)
        expected_epoch = data["expected_epoch"]
        epoch_path_p = Path(epoch_path)
        request_id = data["request_id"]
        idempotency_key = data["idempotency_key"]
        actor_key_id = data["actor_key_id"]
        reason_code = data["reason_code"]

        try:
            lock_fd = _acquire_epoch_lock(epoch_path_p)
        except OSError as exc:
            return _bump_deny(DENY_LOCK_UNAVAILABLE, exc.__class__.__name__)

        try:
            journal_dir, by_request_id_dir, by_idempotency_key_dir = _derive_state_dirs(epoch_path_p)

            # Step 1 (design §3.1) -- read the durable epoch, typed
            # unavailable deny, never a silent 0.
            try:
                current = read_epoch(epoch_path_p)
            except EpochStoreError as exc:
                return _bump_deny(exc.reason, exc.detail)

            # Stale-bump / optimistic-concurrency deny -- stateless, no
            # index/journal state touched either way (unchanged from the
            # pre-C6d order).
            if current != expected_epoch:
                return _bump_deny(
                    DENY_EPOCH_MISMATCH,
                    f"expected={expected_epoch} actual={current}",
                )

            entry_id = _entry_id(request_id, idempotency_key)
            rid_index_path = by_request_id_dir / _sha256_hex(request_id)
            idem_index_path = by_idempotency_key_dir / _sha256_hex(idempotency_key)

            # Step 2 -- reserve BOTH uniqueness identities.
            rid_created = _create_exclusive_json(rid_index_path, {"entry_id": entry_id}, 0o600)
            if rid_created:
                idem_created = _create_exclusive_json(idem_index_path, {"entry_id": entry_id}, 0o600)
                if not idem_created:
                    # Partial reservation (Finding 4 case 2) -- roll back
                    # the index THIS call just created, immediately, before
                    # resolving the pre-existing one.
                    _release_index_if_points_to(rid_index_path, entry_id)
                    _, idem_data = _load_json_or_none(idem_index_path)
                    stored_entry_id = idem_data.get("entry_id") if isinstance(idem_data, Mapping) else None
                    if not isinstance(stored_entry_id, str) or not stored_entry_id:
                        return _bump_deny(DENY_QUARANTINED, "idempotency-key-index-unreadable")
                    return resolve(
                        stored_entry_id, epoch_path_p, journal_dir,
                        by_request_id_dir, by_idempotency_key_dir,
                        presented=(request_id, idempotency_key),
                    )
            else:
                # `by-request-id` index already exists -- this is a replay-,
                # recovery-, or conflict-path. The incoming call's OWN
                # `entry_id` is NOT assumed to equal the stored one; read the
                # pre-existing index's stored pointer and hand off to
                # `resolve()`. Never mutate the epoch on this branch.
                _, rid_data = _load_json_or_none(rid_index_path)
                stored_entry_id = rid_data.get("entry_id") if isinstance(rid_data, Mapping) else None
                if not isinstance(stored_entry_id, str) or not stored_entry_id:
                    return _bump_deny(DENY_QUARANTINED, "request-id-index-unreadable")
                return resolve(
                    stored_entry_id, epoch_path_p, journal_dir,
                    by_request_id_dir, by_idempotency_key_dir,
                    presented=(request_id, idempotency_key),
                )

            # Step 3 -- establish the write-ahead intent for `entry_id`
            # (reached ONLY on the fresh both-indexes-created path).
            journal_path = journal_dir / entry_id
            exists, existing_entry = _load_json_or_none(journal_path)
            new_epoch = current + 1
            moment = now or datetime.now(timezone.utc)
            if not exists:
                fresh_entry: dict[str, Any] = {
                    "request_id": request_id,
                    "idempotency_key": idempotency_key,
                    "actor_key_id": actor_key_id,
                    "reason_code": reason_code,
                    "old_epoch": current,
                    "new_epoch": new_epoch,
                    "phase": "intent",
                    "attempt_gen": 0,
                    "issued_at_authority": _iso(moment),
                    "committed_at": None,
                }
                created = _create_exclusive_json(journal_path, fresh_entry, 0o640)
                if not created:
                    # Impossible after a FRESH dual-index reservation this
                    # same call just made -- torn state, never fabricated.
                    return _bump_deny(DENY_QUARANTINED, "journal-create-raced-fresh-reservation")
            elif isinstance(existing_entry, Mapping) and existing_entry.get("phase") == "aborted":
                # The deterministic `aborted` -> `intent` tombstone reuse
                # (Finding 4 case 1) -- no `O_EXCL` on this pathname, so a
                # retry is never blocked by its own prior tombstone.
                prior_gen = existing_entry.get("attempt_gen", 0)
                fresh_entry = dict(existing_entry)
                fresh_entry.update({
                    "phase": "intent",
                    "attempt_gen": (prior_gen if isinstance(prior_gen, int) else 0) + 1,
                    "old_epoch": current,
                    "new_epoch": new_epoch,
                    "actor_key_id": actor_key_id,
                    "reason_code": reason_code,
                    "issued_at_authority": _iso(moment),
                    "committed_at": None,
                })
                _atomic_rewrite_journal_entry(journal_path, fresh_entry)
            else:
                # present in intent/committed here => impossible after a
                # fresh index reservation => torn state (only reachable
                # through recover()'s resolve() calls, never this branch).
                return _bump_deny(DENY_QUARANTINED, "journal-present-after-fresh-reservation")

            # Step 4 -- the epoch CAS. THE sole durable commit point.
            try:
                _write_epoch_atomic(epoch_path_p, new_epoch)
            except OSError as exc:
                return _bump_deny(DENY_EPOCH_WRITE_FAILED, exc.__class__.__name__)

            # Step 5 -- phase commit. The committed journal entry IS the
            # durable receipt. `audit_pending` is persisted True here --
            # the audit append has not been attempted yet -- so a crash
            # between this write and step 6 (design §5 vector h) leaves
            # the durable entry correctly marked as not-yet-audited,
            # never silently defaulting to `False` on reconstruction.
            committed_entry = dict(fresh_entry)
            committed_entry["phase"] = "committed"
            committed_entry["committed_at"] = _iso(moment)
            committed_entry["audit_pending"] = True
            _atomic_rewrite_journal_entry(journal_path, committed_entry)

            receipt: dict[str, Any] = {
                "old_epoch": current,
                "new_epoch": new_epoch,
                "actor_key_id": actor_key_id,
                "reason_code": reason_code,
                "request_id": request_id,
                "idempotency_key": idempotency_key,
                "committed_at": committed_entry["committed_at"],
                "audit_pending": False,
            }
            # Step 6 -- best-effort projection; never blocks or reverses
            # the already-durable epoch CAS/journal commit. On success,
            # durably clear `audit_pending` in the journal entry now
            # (design §5 vector h's "audit reconciled" outcome) so a
            # LATER `resolve()`/`recover()` never has to retry a bump
            # that already succeeded. On failure, the entry stays
            # persisted `audit_pending=True` (already written above) for
            # `recover()`/`resolve()` to retry -- fail-closed, never
            # silently cleared without a confirmed append.
            try:
                _append_audit_receipt(epoch_path_p, receipt)
            except OSError:
                receipt["audit_pending"] = True
            else:
                committed_entry["audit_pending"] = False
                _atomic_rewrite_journal_entry(journal_path, committed_entry)

            return {"ok": True, "reason": BUMP_OK, "detail": "", "receipt": receipt}
        finally:
            _release_epoch_lock(lock_fd)
    except Exception as exc:  # noqa: BLE001 — total function, never raises into the caller
        return _bump_deny(DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")
