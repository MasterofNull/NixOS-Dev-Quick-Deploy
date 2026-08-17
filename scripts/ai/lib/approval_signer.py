"""WebAuthn-gated signing-service CORE — Approval Control Plane P1 (pure
library; no socket server, no systemd, no key provisioning here).

Implements `.agents/plans/approval-control-plane/ACP-P1-DESIGN-20260816.md`
(authoritative — including both review-fold sections: local Qwen `6so7v7`
findings 4a/4b/3, and the Antigravity REQUEST-REVISION findings, of which
CRITICAL finding 2 is already fixed upstream in `approval_request.py`
(`request_id` is bound into `CANONICAL_FIELDS`) and hardenings 3/4/5 are
folded below). A future confined `acp-signer` UDS service wraps
`ApprovalSigner` 1:1 per connection; this module opens no socket, reads no
`/run/secrets` itself (the owner Ed25519 private key is handed in as
`owner_key: bytes` by that future service wrapper), and provisions no
credentials (registration — writing a NEW entry into the credential
allowlist — is out of scope; this module only ever READS the allowlist).

The one job (design "Architecture"): an agent submits a `request_id`. A
human taps their security key. This module returns an Ed25519 signature
over that request's `canonical_hash` — and ONLY then. No assertion -> no
signature. Wrong/replayed/stale assertion -> no signature. Agent-substituted
payload -> impossible: `sign_request`'s ONLY caller-supplied identifier is
`request_id`; the record itself is always fetched by this module through
the injected `load_record` callable (WYSIWYS — design invariant 1).

Two-step flow (the real WebAuthn ceremony needs a challenge to exist BEFORE
an assertion can be produced over it, so "the whole gated flow" the design
describes is necessarily two calls, not one):
  1. `ApprovalSigner.begin_challenge(request_id, load_record=...)` — fetches
     the record, validates it, recomputes `canonical_hash` (abort on
     drift), derives a fresh per-session `nonce`-bound WebAuthn challenge
     (`derive_challenge`), and persists a short-TTL "a challenge is pending
     for this request_id" record. Returns the raw challenge bytes for
     whatever produces the assertion (P2 web surface / P4 CLI — neither
     built yet; the test suite's software authenticator stands in for P1).
  2. `ApprovalSigner.sign_request(request_id, assertion, load_record=...,
     owner_key=...)` — re-fetches the record itself (WYSIWYS, defends
     against the record being tampered between step 1 and step 2),
     re-verifies everything from scratch, verifies the assertion against
     the SAME challenge derived in step 1 via the real `python-fido2`
     server API, burns the single-use challenge ledger and records the
     append-only executed-request ledger BEFORE ever touching the private
     key, then — and only then — signs.

Non-negotiable invariants carried over from the design packet:
  - WYSIWYS: `sign_request`'s only identifying input is `request_id`; bytes
    signed are always `compute_hash(record)` recomputed from the record
    THIS module loaded, never a caller-supplied hash/bytes.
  - Challenge bound to request + single-use: `derive_challenge` binds
    `canonical_hash` (which already binds `request_id` per the P0 fix) +
    `request_id` again + a per-session server `nonce`; the burn ledger is
    keyed on `request_id` (not `canonical_hash` — two distinct requests
    with identical content must not share a replay slot).
  - No agent-forceable downgrade: there is no fallback signing path in this
    module. Any verification failure is a typed denial that signs nothing.
  - Status is not an authorization signal: `verify_execution_authorization`
    (the executor-side counterpart) checks a valid owner signature over
    `canonical_hash`, never `record["status"]`.

Antigravity hardenings folded here:
  - [hardening 5] `sign_request` checks BOTH the executed-request ledger and
    the challenge-burn ledger, keyed on `request_id` alone, BEFORE loading
    the record or touching any verification logic — a re-submitted
    already-signed/executed `request_id` aborts immediately.
  - [hardening 3] `SigningSessionGuard` enforces max-1-concurrent-session +
    a sliding-window rate limit on `begin_challenge` (the expensive
    "wait for a human tap" phase) — a simple typed guard; the future UDS
    server is what actually serializes concurrent connections through it.
  - [hardening 4 / local finding 3, THE LOAD-BEARING ONE] There is NO
    software/virtual WebAuthn authenticator anywhere in this module, no
    import of `fido2.mock` or any authenticator-simulation code, and no
    runtime env/config flag that could summon one. The only thing this
    module does with `python-fido2` is SERVER-SIDE assertion verification
    (`fido2.server.Fido2Server`) against a caller-supplied
    `fido2.webauthn.AuthenticationResponse`. The software authenticator
    that PRODUCES test assertions lives exclusively in
    `scripts/testing/test-approval-signer.py`.

Scope fence (design "Scope fence" + task bounds): no web UI, no
lost-authenticator recovery, no headless CLI, no runbook automation engine,
no UDS socket server, no Nix/systemd module, no declarative FIDO2 udev, no
live credential registration/provisioning. Pure lib + the class a future
service wraps.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Optional

# Crypto backends are imported crypto-deferred-tolerant: this module exposes its
# typed constants (DENY_*/SIGN_OK/CHALLENGE_OK), record + ledger logic to any
# importer WITHOUT requiring the crypto stack — e.g. the dashboard approval route
# in crypto-deferred dev-mode runs under a bare python that has neither fido2 nor
# cryptography. The real signing/verification methods below use these names and
# require the deps to be importable when actually INVOKED (i.e. once crypto is
# activated); `_CRYPTO_AVAILABLE` gates any runtime path that needs them. No
# `fido2.mock` is ever imported (test_production_module_excludes_software_authenticator).
try:
    import fido2.cose as cose
    import fido2.server as srv
    import fido2.webauthn as w
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    _CRYPTO_AVAILABLE = True
except ImportError:  # crypto-deferred dev-mode host (bare python, no fido2/cryptography)
    cose = srv = w = None  # type: ignore
    Ed25519PrivateKey = Ed25519PublicKey = None  # type: ignore
    _CRYPTO_AVAILABLE = False

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import approval_request as AR  # noqa: E402

# --------------------------------------------------------------------------
# FIDO2 credential allowlist — mirrors config/aqos/lease-signer-keys.json /
# c6-scheduler-signer-keys.json's `{schema_version, revision, keys:[...]}`
# shape (renamed `credentials` here). Public-only; NO private material.
# Registration (writing a NEW entry) is out of scope for this module — it
# only ever READS this file, fresh on every call, so a revoked credential
# denies immediately (same "status re-checked on every call" discipline as
# `revocation_epoch._verify_signature`).
# --------------------------------------------------------------------------

CREDENTIAL_ALLOWLIST_SCHEMA_VERSION = "1"
CREDENTIAL_KEYS = frozenset({"credential_id", "public_key", "sign_count", "status"})
CREDENTIAL_STATUS_ACTIVE = "active"
CREDENTIAL_STATUS_VALUES = ("active", "revoked")

# Generous bound on the allowlist file — it is small and hand-provisioned,
# never agent-writable; this is a defense-in-depth cap, not a sizing budget.
_MAX_ALLOWLIST_FILE_BYTES = 1 << 20


def load_credential_allowlist(path: Any) -> Optional[dict[str, dict]]:
    """Read + validate the FIDO2 credential allowlist at `path`. Returns
    `{credential_id_hex: entry}` or `None` (fail-closed — deny, no
    credential can possibly match) on ANY malformed shape: missing file,
    bad JSON, wrong schema_version, wrong per-entry key set, malformed hex,
    negative/bool `sign_count`, unknown `status`, or a duplicate
    `credential_id`. Never raises."""
    try:
        raw_bytes = Path(path).read_bytes()
    except OSError:
        return None
    if len(raw_bytes) > _MAX_ALLOWLIST_FILE_BYTES:
        return None
    try:
        doc = json.loads(raw_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return None
    if not isinstance(doc, dict) or doc.get("schema_version") != CREDENTIAL_ALLOWLIST_SCHEMA_VERSION:
        return None
    entries = doc.get("credentials")
    if not isinstance(entries, list):
        return None

    out: dict[str, dict] = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry.keys()) != CREDENTIAL_KEYS:
            return None
        cred_id = entry.get("credential_id")
        pubkey = entry.get("public_key")
        sign_count = entry.get("sign_count")
        status = entry.get("status")
        if not isinstance(cred_id, str) or not cred_id or re.fullmatch(r"[0-9a-f]+", cred_id) is None:
            return None
        if not isinstance(pubkey, str) or re.fullmatch(r"[0-9a-f]{64}", pubkey) is None:
            return None
        if isinstance(sign_count, bool) or not isinstance(sign_count, int) or sign_count < 0:
            return None
        if status not in CREDENTIAL_STATUS_VALUES:
            return None
        if cred_id in out:
            return None
        out[cred_id] = entry
    return out


# --------------------------------------------------------------------------
# Challenge derivation (design "Architecture" step 3, Antigravity finding 2
# reinforced here). Deterministic, domain-separated, pure.
# --------------------------------------------------------------------------

CHALLENGE_DOMAIN_TAG = b"aq.approval-signer-challenge/1"
SIGNATURE_DOMAIN_TAG = b"aq.approval-signer.owner-signature/1"
NONCE_BYTES = 32
CHALLENGE_TTL = timedelta(seconds=120)  # local Qwen finding 4b


def derive_challenge(canonical_hash: str, request_id: str, nonce: bytes) -> bytes:
    """Deterministic 32-byte WebAuthn challenge binding `canonical_hash`
    (the P0 record hash, which already includes `request_id` per the
    Antigravity finding-2 fix) + `request_id` again (explicit, defense in
    depth) + a per-session server `nonce`. Same inputs -> byte-identical
    output, always; a different `nonce` (fresh every `begin_challenge`
    call, per Antigravity finding 2's "inherently per request instance")
    -> an unrelated challenge, so no two signing sessions ever share one
    even for content-identical sibling requests."""
    if not isinstance(canonical_hash, str) or not canonical_hash:
        raise ValueError("canonical_hash_required")
    if not isinstance(request_id, str) or not request_id:
        raise ValueError("request_id_required")
    if not isinstance(nonce, (bytes, bytearray)) or len(nonce) < 16:
        raise ValueError("nonce_too_short")
    body = canonical_hash.encode("utf-8") + b"\x00" + request_id.encode("utf-8") + b"\x00" + bytes(nonce)
    return hashlib.sha256(CHALLENGE_DOMAIN_TAG + b"\x00" + body).digest()


def _signable_bytes(canonical_hash: str) -> bytes:
    """Domain-separated bytes actually Ed25519-signed/verified for
    execution authorization — never the bare hash string, so this
    signature can never be replayed as a signature over some unrelated
    hash-preimage protocol elsewhere in the codebase."""
    return SIGNATURE_DOMAIN_TAG + b"\x00" + canonical_hash.encode("utf-8")


# --------------------------------------------------------------------------
# Time helpers (mirrors approval_request/revocation_epoch)
# --------------------------------------------------------------------------


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str) -> datetime:
    v = value[:-1] + "+00:00" if value.endswith("Z") else value
    dt = datetime.fromisoformat(v)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


# --------------------------------------------------------------------------
# Durable single-use ledger — reused for BOTH the challenge-burn ledger and
# the executed-request ledger (two independently-directoried instances, so
# a rewrite of one never implies a rewrite of the other — Antigravity
# hardening 5's "defends against execution-history rewrite"). Mirrors
# `revocation_epoch.DurableReplayLedger`'s O_EXCL + fsync(file)+fsync(dir)
# atomicity/durability pattern; reimplemented (not imported) to keep this
# confined-service bundle self-contained (the `lease_signing_authority.py`
# WR-3 lesson), keyed on a single `request_id` string instead of a tuple.
# --------------------------------------------------------------------------


class SingleUseLedger:
    """One empty(-ish) marker file per consumed `request_id`, named
    `sha256(request_id)` under `ledger_dir`. `check_and_record` is a single
    atomic `os.open(O_CREAT|O_EXCL)`: exactly one caller for a given
    `request_id` ever observes `True`; every later call — including after a
    process restart, since the state lives on disk, not in memory —
    observes `False`. FAIL-CLOSED: any `OSError` other than `EEXIST`
    propagates (caller turns it into a denial, never a silent go-ahead)."""

    def __init__(self, ledger_dir: Any) -> None:
        self._dir = str(ledger_dir)
        os.makedirs(self._dir, mode=0o700, exist_ok=True)

    def _path(self, request_id: str) -> str:
        digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        return os.path.join(self._dir, digest)

    def is_recorded(self, request_id: str) -> bool:
        return os.path.exists(self._path(request_id))

    def check_and_record(self, request_id: str) -> bool:
        path = self._path(request_id)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
        except FileExistsError:
            return False
        try:
            payload = json.dumps(
                {"request_id": request_id, "recorded_at": _iso(datetime.now(timezone.utc))},
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
        return True


# --------------------------------------------------------------------------
# Pending-challenge store — mutable/overwritable, NOT the single-use ledger.
# Losing this (e.g. a restart mid-flow, before any assertion is verified)
# only means the agent must call `begin_challenge` again; it never weakens
# security, since the single-use ledgers above are what actually gate
# signing.
# --------------------------------------------------------------------------


class PendingChallengeStore:
    def __init__(self, store_dir: Any) -> None:
        self._dir = str(store_dir)
        os.makedirs(self._dir, mode=0o700, exist_ok=True)

    def _path(self, request_id: str) -> str:
        digest = hashlib.sha256(request_id.encode("utf-8")).hexdigest()
        return os.path.join(self._dir, digest)

    def put(self, request_id: str, payload: Mapping[str, Any]) -> None:
        path = self._path(request_id)
        fd, tmp_path = tempfile.mkstemp(dir=self._dir, prefix=".pending.", suffix=".tmp")
        try:
            os.write(fd, json.dumps(dict(payload), sort_keys=True).encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
        dir_fd = os.open(self._dir, os.O_DIRECTORY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)

    def get(self, request_id: str) -> Optional[dict]:
        try:
            raw = Path(self._path(request_id)).read_bytes()
        except OSError:
            return None
        try:
            doc = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return None
        return doc if isinstance(doc, dict) else None

    def clear(self, request_id: str) -> None:
        try:
            os.unlink(self._path(request_id))
        except OSError:
            pass


# --------------------------------------------------------------------------
# Rate-limit / max-concurrent-session guard (Antigravity hardening 3) — a
# simple typed guard. In-process, single-service-instance scope: the future
# confined UDS server runs ONE `ApprovalSigner` per process and is expected
# to serialize every connection's `begin_challenge`/`sign_request` calls
# through this SAME guard object, so its process-lifetime state is exactly
# the intended scope (one live signing session across the whole service,
# not per-connection).
# --------------------------------------------------------------------------

GUARD_OK = "ok"
DENY_RATE_LIMITED = "rate-limited"
DENY_CONCURRENT_SESSION = "concurrent-session-active"


@dataclass(frozen=True)
class GuardVerdict:
    ok: bool
    reason: str


class SigningSessionGuard:
    def __init__(
        self,
        *,
        max_concurrent: int = 1,
        rate_limit_window: timedelta = timedelta(seconds=60),
        rate_limit_max: int = 5,
    ) -> None:
        self._active = 0
        self._max_concurrent = max_concurrent
        self._window = rate_limit_window
        self._max_per_window = rate_limit_max
        self._events: list[datetime] = []

    def try_begin(self, now: Optional[datetime] = None) -> GuardVerdict:
        moment = now or datetime.now(timezone.utc)
        cutoff = moment - self._window
        self._events = [t for t in self._events if t > cutoff]
        if len(self._events) >= self._max_per_window:
            return GuardVerdict(False, DENY_RATE_LIMITED)
        if self._active >= self._max_concurrent:
            return GuardVerdict(False, DENY_CONCURRENT_SESSION)
        self._active += 1
        self._events.append(moment)
        return GuardVerdict(True, GUARD_OK)

    def end(self) -> None:
        """Idempotent release — safe to call even if a session was never
        successfully acquired (`sign_request` always calls this in a
        `finally` block, whether or not `begin_challenge` ran first)."""
        if self._active > 0:
            self._active -= 1


# --------------------------------------------------------------------------
# Typed, safe-to-log denial vocabulary for the two gated operations.
# --------------------------------------------------------------------------

CHALLENGE_OK = "ok"
SIGN_OK = "ok"

DENY_INVALID_REQUEST_ID = "request-id-invalid"
DENY_NOT_FOUND = "request-not-found"
DENY_RECORD_INVALID = "record-invalid"
DENY_HASH_DRIFT = "canonical-hash-drift"
DENY_EXECUTED_REPLAY = "already-executed"
DENY_CHALLENGE_REPLAY = "challenge-already-used"
DENY_NO_PENDING_CHALLENGE = "no-pending-challenge"
DENY_CHALLENGE_EXPIRED = "challenge-expired"
DENY_ASSERTION_MISSING = "assertion-missing"
DENY_ASSERTION_MALFORMED = "assertion-malformed"
DENY_ASSERTION_INVALID = "assertion-verification-failed"
DENY_UNKNOWN_CREDENTIAL = "unknown-credential"
DENY_CREDENTIAL_NOT_ACTIVE = "credential-not-active"
DENY_CLONE_SUSPECTED = "sign-count-not-increasing"
DENY_ALLOWLIST_UNAVAILABLE = "credential-allowlist-unavailable"
DENY_LEDGER_UNAVAILABLE = "ledger-unavailable"
DENY_INTERNAL = "internal-error"


@dataclass(frozen=True)
class ChallengeVerdict:
    ok: bool
    reason: str
    detail: str = ""
    challenge: Optional[bytes] = None
    expires_at: Optional[str] = None


@dataclass(frozen=True)
class SignVerdict:
    ok: bool
    reason: str
    detail: str = ""
    signature: Optional[str] = None
    canonical_hash: Optional[str] = None


# --------------------------------------------------------------------------
# verify_execution_authorization — the executor-side check (design
# invariant 6): a valid owner Ed25519 signature over `canonical_hash` IS
# the authorization to execute. Deliberately does NOT look at
# `record["status"]` at all — status is bookkeeping, never the trust
# source. Total function: never raises.
# --------------------------------------------------------------------------

AUTH_OK = "ok"
AUTH_DENY_RECORD_MALFORMED = "record-malformed"
AUTH_DENY_SIGNATURE_MALFORMED = "signature-malformed"
AUTH_DENY_KEY_MALFORMED = "owner-key-malformed"
AUTH_DENY_BAD_SIGNATURE = "bad-signature"
AUTH_DENY_INTERNAL = "internal-error"


@dataclass(frozen=True)
class AuthorizationVerdict:
    ok: bool
    reason: str
    detail: str = ""


def verify_execution_authorization(
    record: Any, signature: Any, owner_public_key: Any
) -> AuthorizationVerdict:
    """Total, never-raising verdict: does `signature` cover
    `compute_hash(record)` under `owner_public_key`? This is the ONLY
    authorization signal the P1 executor contract trusts (design invariant
    6) — `record["status"]` is never consulted here. `signature` and
    `owner_public_key` may be raw `bytes` or a hex `str`."""
    try:
        try:
            canonical_hash = AR.compute_hash(record)
        except Exception as exc:  # noqa: BLE001 - malformed record, not a crash
            return AuthorizationVerdict(False, AUTH_DENY_RECORD_MALFORMED, exc.__class__.__name__)

        try:
            sig_bytes = bytes.fromhex(signature) if isinstance(signature, str) else bytes(signature)
        except (ValueError, TypeError) as exc:
            return AuthorizationVerdict(False, AUTH_DENY_SIGNATURE_MALFORMED, exc.__class__.__name__)

        try:
            key_bytes = (
                bytes.fromhex(owner_public_key)
                if isinstance(owner_public_key, str)
                else bytes(owner_public_key)
            )
            public_key = Ed25519PublicKey.from_public_bytes(key_bytes)
        except (ValueError, TypeError) as exc:
            return AuthorizationVerdict(False, AUTH_DENY_KEY_MALFORMED, exc.__class__.__name__)

        try:
            public_key.verify(sig_bytes, _signable_bytes(canonical_hash))
        except Exception:  # noqa: BLE001 - InvalidSignature or any verify fault -> deny
            return AuthorizationVerdict(False, AUTH_DENY_BAD_SIGNATURE)

        return AuthorizationVerdict(True, AUTH_OK)
    except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
        return AuthorizationVerdict(False, AUTH_DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")


# --------------------------------------------------------------------------
# ApprovalSigner — the signing-service CORE. A future confined UDS server
# wraps ONE instance of this class per process and calls `begin_challenge`/
# `sign_request` per connection, holding the owner Ed25519 private key
# itself (read from `/run/secrets`, never from this module) and passing it
# in as `owner_key` only inside `sign_request`.
# --------------------------------------------------------------------------


class ApprovalSigner:
    def __init__(
        self,
        *,
        credential_allowlist_path: Any,
        challenge_store_dir: Any,
        challenge_ledger_dir: Any,
        executed_ledger_dir: Any,
        rp_id: str,
        challenge_ttl: timedelta = CHALLENGE_TTL,
        max_concurrent_sessions: int = 1,
        rate_limit_window: timedelta = timedelta(seconds=60),
        rate_limit_max: int = 5,
    ) -> None:
        if not isinstance(rp_id, str) or not rp_id:
            raise ValueError("rp_id_required")
        self._allowlist_path = str(credential_allowlist_path)
        self._pending = PendingChallengeStore(challenge_store_dir)
        self._challenge_ledger = SingleUseLedger(challenge_ledger_dir)
        self._executed_ledger = SingleUseLedger(executed_ledger_dir)
        self._rp_id = rp_id
        self._ttl = challenge_ttl
        self._guard = SigningSessionGuard(
            max_concurrent=max_concurrent_sessions,
            rate_limit_window=rate_limit_window,
            rate_limit_max=rate_limit_max,
        )

    # -- step 1: derive + persist a fresh challenge for `request_id` -----

    def begin_challenge(
        self,
        request_id: str,
        *,
        load_record: Callable[[str], Optional[Mapping[str, Any]]],
        now: Optional[datetime] = None,
    ) -> ChallengeVerdict:
        """Design architecture steps 1-3: fetch the record itself, re-
        validate + recompute `canonical_hash` (abort on drift), derive a
        fresh nonce-bound challenge, and persist a short-TTL pending-
        challenge record. Guarded by `SigningSessionGuard` (Antigravity
        hardening 3) — the guard slot acquired here is released either by
        an early deny below or by the matching `sign_request` call."""
        moment = now or datetime.now(timezone.utc)
        session = self._guard.try_begin(now=moment)
        if not session.ok:
            # Never acquired -> nothing to release.
            return ChallengeVerdict(False, session.reason)
        try:
            if not isinstance(request_id, str) or not request_id:
                self._guard.end()
                return ChallengeVerdict(False, DENY_INVALID_REQUEST_ID)

            if self._executed_ledger.is_recorded(request_id):
                self._guard.end()
                return ChallengeVerdict(False, DENY_EXECUTED_REPLAY)
            if self._challenge_ledger.is_recorded(request_id):
                self._guard.end()
                return ChallengeVerdict(False, DENY_CHALLENGE_REPLAY)

            record = load_record(request_id)
            if record is None:
                self._guard.end()
                return ChallengeVerdict(False, DENY_NOT_FOUND)
            verdict = AR.validate(record)
            if not verdict.ok:
                self._guard.end()
                return ChallengeVerdict(False, DENY_RECORD_INVALID, verdict.reason)
            canonical_hash = AR.compute_hash(record)
            stored_hash = record["binding"]["canonical_hash"]
            if canonical_hash != stored_hash:
                self._guard.end()
                return ChallengeVerdict(False, DENY_HASH_DRIFT)

            nonce = os.urandom(NONCE_BYTES)
            try:
                challenge = derive_challenge(canonical_hash, request_id, nonce)
            except ValueError as exc:
                self._guard.end()
                return ChallengeVerdict(False, DENY_INTERNAL, exc.args[0] if exc.args else "")
            expires_at = _iso(moment + self._ttl)
            self._pending.put(
                request_id,
                {
                    "request_id": request_id,
                    "nonce": nonce.hex(),
                    "canonical_hash": canonical_hash,
                    "issued_at": _iso(moment),
                    "expires_at": expires_at,
                },
            )
            # SUCCESS: the guard slot stays HELD — this is the "active
            # signing session" the guard exists to bound. The matching
            # `sign_request` call releases it (in its own `finally`),
            # whether that call ultimately succeeds or is denied.
            return ChallengeVerdict(True, CHALLENGE_OK, challenge=challenge, expires_at=expires_at)
        except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
            self._guard.end()
            return ChallengeVerdict(False, DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")

    # -- step 2: verify the assertion + sign, or deny and sign nothing ---

    def sign_request(
        self,
        request_id: str,
        assertion: Any,
        *,
        load_record: Callable[[str], Optional[Mapping[str, Any]]],
        owner_key: bytes,
        now: Optional[datetime] = None,
    ) -> SignVerdict:
        """The whole gated flow (design architecture steps 1-2, 4-7). ANY
        failure returns a typed denial and signs NOTHING (fail closed, no
        downgrade path). Releases the `SigningSessionGuard` slot on every
        exit, whether or not `begin_challenge` was actually called first
        for this `request_id` (idempotent release)."""
        moment = now or datetime.now(timezone.utc)
        try:
            if not isinstance(request_id, str) or not request_id:
                return SignVerdict(False, DENY_INVALID_REQUEST_ID)

            # Antigravity hardening 5 — ABORT before any verification.
            if self._executed_ledger.is_recorded(request_id):
                return SignVerdict(False, DENY_EXECUTED_REPLAY)
            if self._challenge_ledger.is_recorded(request_id):
                return SignVerdict(False, DENY_CHALLENGE_REPLAY)

            if assertion is None:
                return SignVerdict(False, DENY_ASSERTION_MISSING)
            if not isinstance(assertion, w.AuthenticationResponse):
                return SignVerdict(False, DENY_ASSERTION_MALFORMED, type(assertion).__name__)

            # WYSIWYS — the ONLY caller-supplied identifier is request_id;
            # the record is always fetched by this module itself.
            record = load_record(request_id)
            if record is None:
                return SignVerdict(False, DENY_NOT_FOUND)
            verdict = AR.validate(record)
            if not verdict.ok:
                return SignVerdict(False, DENY_RECORD_INVALID, verdict.reason)
            canonical_hash = AR.compute_hash(record)
            stored_hash = record["binding"]["canonical_hash"]
            if canonical_hash != stored_hash:
                return SignVerdict(False, DENY_HASH_DRIFT)

            pending = self._pending.get(request_id)
            if pending is None:
                return SignVerdict(False, DENY_NO_PENDING_CHALLENGE)
            if pending.get("canonical_hash") != canonical_hash:
                # The record changed between begin_challenge and sign_request
                # (or a stale/foreign pending entry) -> never trust it.
                return SignVerdict(False, DENY_HASH_DRIFT, "pending-session-mismatch")
            try:
                expires_at = _parse_iso(pending["expires_at"])
                nonce = bytes.fromhex(pending["nonce"])
            except (KeyError, TypeError, ValueError):
                return SignVerdict(False, DENY_NO_PENDING_CHALLENGE, "malformed-pending")
            if moment > expires_at:
                return SignVerdict(False, DENY_CHALLENGE_EXPIRED)
            expected_challenge = derive_challenge(canonical_hash, request_id, nonce)

            allowlist = load_credential_allowlist(self._allowlist_path)
            if allowlist is None:
                return SignVerdict(False, DENY_ALLOWLIST_UNAVAILABLE)
            credential_id_hex = assertion.raw_id.hex()
            entry = allowlist.get(credential_id_hex)
            if entry is None:
                return SignVerdict(False, DENY_UNKNOWN_CREDENTIAL)
            if entry["status"] != CREDENTIAL_STATUS_ACTIVE:
                return SignVerdict(False, DENY_CREDENTIAL_NOT_ACTIVE)

            cose_key = cose.EdDSA(
                {1: 1, 3: cose.EdDSA.ALGORITHM, -1: 6, -2: bytes.fromhex(entry["public_key"])}
            )
            attested = w.AttestedCredentialData.create(
                b"\x00" * 16, bytes.fromhex(entry["credential_id"]), cose_key
            )

            server = srv.Fido2Server(w.PublicKeyCredentialRpEntity(name=self._rp_id, id=self._rp_id))
            try:
                _options, state = server.authenticate_begin(
                    credentials=[attested],
                    user_verification=w.UserVerificationRequirement.REQUIRED,
                    challenge=expected_challenge,
                )
                server.authenticate_complete(state, credentials=[attested], response=assertion)
            except Exception as exc:  # noqa: BLE001 - any fido2 verify fault -> typed denial
                return SignVerdict(False, DENY_ASSERTION_INVALID, exc.__class__.__name__)

            # Anti-clone (WebAuthn 6.1.1): only enforced when BOTH the
            # allowlist's last-known counter and this assertion's counter
            # are tracked (nonzero) — a 0 counter means the authenticator
            # does not implement one, per spec, and is not itself a fault.
            # Persisting the bumped counter back into the allowlist is a
            # registration/write-back concern, out of this module's "no
            # live provisioning" scope (see module docstring) — this check
            # therefore degrades gracefully to "checked when tracked"
            # rather than being silently absent.
            new_counter = assertion.response.authenticator_data.counter
            old_counter = entry.get("sign_count", 0)
            if old_counter > 0 and new_counter > 0 and new_counter <= old_counter:
                return SignVerdict(False, DENY_CLONE_SUSPECTED)

            # Burn BOTH ledgers BEFORE the private key is ever touched
            # (design step 6 precedes step 7) — any ledger fault here means
            # we sign NOTHING.
            if not self._challenge_ledger.check_and_record(request_id):
                return SignVerdict(False, DENY_CHALLENGE_REPLAY)
            if not self._executed_ledger.check_and_record(request_id):
                return SignVerdict(False, DENY_EXECUTED_REPLAY)

            private_key = Ed25519PrivateKey.from_private_bytes(owner_key)
            signature = private_key.sign(_signable_bytes(canonical_hash)).hex()

            self._pending.clear(request_id)
            return SignVerdict(True, SIGN_OK, signature=signature, canonical_hash=canonical_hash)
        except Exception as exc:  # noqa: BLE001 - total function, never raises into the caller
            return SignVerdict(False, DENY_INTERNAL, f"unhandled:{exc.__class__.__name__}")
        finally:
            self._guard.end()
