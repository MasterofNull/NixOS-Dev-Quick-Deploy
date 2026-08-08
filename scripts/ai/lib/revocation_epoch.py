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

Flow (verify -> expected-epoch -> replay-ledger -> atomic +1): `apply_bump`
deliberately runs the durable single-use replay-ledger check BEFORE the
epoch mutation (not after, as a narrative read of the design doc's service
description might suggest) so that a replayed `{request_id,
idempotency_key}` is caught with STRICTLY ZERO chance of ever reaching the
mutating write — the ledger check-and-record and the epoch compare-and-swap
both happen under the same exclusive `epoch.lock`, so this ordering is
equivalent-or-safer than write-then-record, never weaker.
"""
from __future__ import annotations

import errno
import fcntl
import hashlib
import json
import os
import re
import stat
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


def _bump_deny(reason: str, detail: str = "") -> dict[str, Any]:
    return {"ok": False, "reason": reason, "detail": detail, "receipt": None}


def apply_bump(
    bump_doc: Any,
    epoch_path: Any,
    ledger: "DurableReplayLedger",
    owner_keys_json_dict: Any,
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Verify -> expected-epoch match -> replay-ledger -> atomic +1 ->
    audit receipt. Returns `{"ok": True, "reason": BUMP_OK, "detail": "",
    "receipt": {...}}` on success, or `{"ok": False, "reason": DENY_*,
    "detail": ..., "receipt": None}` on ANY deny. Total function — never
    raises, never mutates epoch/ledger state on any deny path (see module
    docstring for the ledger's one documented over-denial edge case: a
    later I/O fault AFTER the ledger record but before the epoch write).

    Order (deliberate — see module docstring): `verify_bump` first (no
    state touched), then compare `bump_doc["expected_epoch"]` against
    `read_epoch(epoch_path)` (stale-bump / optimistic-concurrency deny),
    then the durable single-use `ledger.check_and_record` on
    `(request_id, idempotency_key)` (a replay denies here, before any
    mutation), then — and only then — `_write_epoch_atomic` advances the
    epoch by exactly +1. All of this happens under one exclusive
    `epoch.lock` hold."""
    try:
        verdict = verify_bump(bump_doc, owner_keys_json_dict, now=now)
        if not verdict.ok:
            return _bump_deny(verdict.reason, verdict.detail)

        data = dict(bump_doc)
        expected_epoch = data["expected_epoch"]
        epoch_path_p = Path(epoch_path)

        try:
            lock_fd = _acquire_epoch_lock(epoch_path_p)
        except OSError as exc:
            return _bump_deny(DENY_LOCK_UNAVAILABLE, exc.__class__.__name__)

        try:
            try:
                current = read_epoch(epoch_path_p)
            except EpochStoreError as exc:
                return _bump_deny(exc.reason, exc.detail)

            if current != expected_epoch:
                return _bump_deny(
                    DENY_EPOCH_MISMATCH,
                    f"expected={expected_epoch} actual={current}",
                )

            replay_key = (data["request_id"], data["idempotency_key"])
            try:
                first_use = ledger.check_and_record(replay_key)
            except Exception:  # noqa: BLE001 — a faulting ledger fails CLOSED, never open
                return _bump_deny(DENY_LEDGER_UNAVAILABLE)
            if not first_use:
                return _bump_deny(DENY_REPLAY)

            new_epoch = current + 1
            try:
                _write_epoch_atomic(epoch_path_p, new_epoch)
            except OSError as exc:
                return _bump_deny(DENY_EPOCH_WRITE_FAILED, exc.__class__.__name__)

            moment = now or datetime.now(timezone.utc)
            receipt: dict[str, Any] = {
                "old_epoch": current,
                "new_epoch": new_epoch,
                "actor_key_id": data["actor_key_id"],
                "reason_code": data["reason_code"],
                "request_id": data["request_id"],
                "idempotency_key": data["idempotency_key"],
                "committed_at": _iso(moment),
                "audit_pending": False,
            }
            try:
                _append_audit_receipt(epoch_path_p, receipt)
            except OSError:
                receipt["audit_pending"] = True

            return {"ok": True, "reason": BUMP_OK, "detail": "", "receipt": receipt}
        finally:
            _release_epoch_lock(lock_fd)
    except Exception as exc:  # noqa: BLE001 — total function, never raises into the caller
        return _bump_deny(DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")
