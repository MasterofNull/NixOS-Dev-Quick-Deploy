#!/usr/bin/env python3
"""Acceptance tests for the Approval Control Plane P1 signing service core
(`scripts/ai/lib/approval_signer.py`).

Covers the "Test / validation strategy" goals from
`.agents/plans/approval-control-plane/ACP-P1-DESIGN-20260816.md`: wysiwys-
fetch, no-assertion-no-signature, wrong-credential / wrong-challenge,
single-use replay (durable across a simulated restart), tamper-abort,
executed-id-replay-aborts-before-verify, content-identical-different-
request_id -> different signatures, plus `verify_execution_authorization`'s
accept/reject and the rate-limit/concurrency guard. Fully offline: no
network, temp-dir-backed ledgers/allowlist standing in for the confined
service's real state.

WebAuthn crypto is exercised with a REAL software authenticator producing a
REAL assertion over a REAL challenge, verified by the REAL `python-fido2`
server code inside `approval_signer.ApprovalSigner` — never a mocked verify
call. The software authenticator (`_SoftwareAuthenticator` below) is
TEST-ONLY: it exists exclusively in this file, is never imported by
`approval_signer.py` (asserted directly in
`test_production_module_excludes_software_authenticator` below —
Antigravity hardening 4), and there is no env/config flag anywhere that
could summon a software authenticator inside the production module.

`check()` raises `AssertionError` immediately on a failed condition so
`pytest` reports real per-test PASS/FAIL. `main()` runs every `test_*`
function and aggregates failures for a single human-readable summary when
run directly.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

import fido2.webauthn as w  # noqa: E402
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import (  # noqa: E402
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

import approval_request as AR  # noqa: E402
import approval_signer as AS  # noqa: E402

APPROVAL_SIGNER_SOURCE = (LIB_DIR / "approval_signer.py").read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# --------------------------------------------------------------------------
# TEST-ONLY software/virtual WebAuthn authenticator. NEVER imported by
# approval_signer.py — see test_production_module_excludes_software_authenticator.
# --------------------------------------------------------------------------


class _SoftwareAuthenticator:
    """Holds a throwaway Ed25519 keypair + credential id and can produce a
    real `fido2.webauthn.AuthenticationResponse` over a caller-supplied
    challenge, built from the SAME wire-format dataclasses
    `approval_signer.ApprovalSigner` verifies with the real
    `fido2.server.Fido2Server` API — this is a faithful protocol exercise,
    not a mocked verify() call."""

    def __init__(self, *, rp_id: str, credential_id: bytes = None, user_verified: bool = True) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.credential_id = credential_id or os.urandom(32)
        self.rp_id = rp_id
        self.user_verified = user_verified

    @property
    def public_key_hex(self) -> str:
        return self.private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    def allowlist_entry(self, *, status: str = "active", sign_count: int = 0) -> dict:
        return {
            "credential_id": self.credential_id.hex(),
            "public_key": self.public_key_hex,
            "sign_count": sign_count,
            "status": status,
        }

    def get_assertion(
        self,
        challenge: bytes,
        *,
        counter: int = 1,
        origin: str = None,
        user_verified: bool = None,
        credential_id: bytes = None,
    ) -> w.AuthenticationResponse:
        uv = self.user_verified if user_verified is None else user_verified
        rp_id_hash = hashlib.sha256(self.rp_id.encode("utf-8")).digest()
        flags = w.AuthenticatorData.FLAG.UP
        if uv:
            flags = flags | w.AuthenticatorData.FLAG.UV
        auth_data = w.AuthenticatorData.create(rp_id_hash, flags, counter)
        client_data = w.CollectedClientData.create(
            type="webauthn.get", challenge=challenge, origin=origin or f"https://{self.rp_id}"
        )
        signature = self.private_key.sign(bytes(auth_data) + client_data.hash)
        response = w.AuthenticatorAssertionResponse(
            client_data=client_data, authenticator_data=auth_data, signature=signature
        )
        return w.AuthenticationResponse(raw_id=credential_id or self.credential_id, response=response)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _new_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def _fixture_record(request_id: str, *, service: str = "approval-signer-test") -> dict:
    return AR.create_request(
        request_id=request_id,
        created_by="test-suite",
        runbook="restart-service",
        params={"service": service},
    )


class _Env:
    """Fresh temp-dir-backed ledgers/allowlist/record-store + a throwaway
    owner Ed25519 keypair per test."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.allowlist_path = base / "credentials.json"
        self.challenge_store_dir = base / "pending"
        self.challenge_ledger_dir = base / "challenge-ledger"
        self.executed_ledger_dir = base / "executed-ledger"
        self.rp_id = "approval-signer.test"

        self.owner_private = Ed25519PrivateKey.generate()
        self.owner_key_bytes = self.owner_private.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )
        self.owner_public_bytes = self.owner_private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )

        self._store: dict[str, dict] = {}
        self._write_allowlist([])

    def _write_allowlist(self, entries: list) -> None:
        doc = {"schema_version": "1", "revision": 1, "credentials": entries}
        self.allowlist_path.write_text(json.dumps(doc), encoding="utf-8")

    def add_credential(self, entry: dict) -> None:
        entries = json.loads(self.allowlist_path.read_text(encoding="utf-8"))["credentials"]
        entries.append(entry)
        self._write_allowlist(entries)

    def load_record(self, request_id: str):
        return self._store.get(request_id)

    def save_record(self, record: dict) -> None:
        self._store[record["request_id"]] = record

    def signer(self, **overrides) -> AS.ApprovalSigner:
        # Generous concurrency/rate defaults so tests not specifically
        # about SigningSessionGuard aren't accidentally coupled to it.
        kwargs = dict(
            credential_allowlist_path=self.allowlist_path,
            challenge_store_dir=self.challenge_store_dir,
            challenge_ledger_dir=self.challenge_ledger_dir,
            executed_ledger_dir=self.executed_ledger_dir,
            rp_id=self.rp_id,
            max_concurrent_sessions=8,
            rate_limit_max=1000,
        )
        kwargs.update(overrides)
        return AS.ApprovalSigner(**kwargs)


# --------------------------------------------------------------------------
# derive_challenge — pure properties
# --------------------------------------------------------------------------


def test_derive_challenge_properties() -> None:
    h = "a" * 64
    n1, n2 = os.urandom(32), os.urandom(32)
    c1 = AS.derive_challenge(h, "req-1", n1)
    c1_again = AS.derive_challenge(h, "req-1", n1)
    c2 = AS.derive_challenge(h, "req-1", n2)
    c3 = AS.derive_challenge(h, "req-2", n1)
    check(len(c1) == 32, "challenge is not 32 bytes")
    check(c1 == c1_again, "derive_challenge is not deterministic for identical inputs")
    check(c1 != c2, "a different nonce produced the same challenge")
    check(c1 != c3, "a different request_id produced the same challenge")


# --------------------------------------------------------------------------
# sign-happy-path + wysiwys-fetch
# --------------------------------------------------------------------------


def test_sign_happy_path() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    request_id = _new_request_id()
    record = _fixture_record(request_id)
    env.save_record(record)

    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    check(cv.ok, f"begin_challenge failed: {cv.reason} {cv.detail}")
    check(cv.challenge is not None and len(cv.challenge) == 32, "begin_challenge did not return a 32-byte challenge")

    assertion = auth.get_assertion(cv.challenge)
    sv = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(sv.ok, f"sign_request happy path failed: {sv.reason} {sv.detail}")
    check(sv.signature is not None, "successful sign_request returned no signature")
    check(sv.canonical_hash == AR.compute_hash(record), "returned canonical_hash does not match the record")

    # The returned signature really is a valid Ed25519 signature over the
    # domain-separated canonical_hash bytes, under the owner's public key —
    # verified independently of ApprovalSigner's own verify path.
    env.owner_private.public_key().verify(bytes.fromhex(sv.signature), AS._signable_bytes(sv.canonical_hash))

    # Executor-side counterpart accepts it too.
    auth_verdict = AS.verify_execution_authorization(record, sv.signature, env.owner_public_bytes)
    check(auth_verdict.ok, f"verify_execution_authorization rejected a valid signature: {auth_verdict.reason}")


def test_wysiwys_only_request_id_influences_signature() -> None:
    """`sign_request`'s only identifying input is request_id — a caller
    cannot smuggle a different payload in; whatever `load_record` returns
    for that id is what gets signed, regardless of what a compromised
    caller might have wanted."""
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    request_id = _new_request_id()
    record = _fixture_record(request_id, service="the-real-service")
    env.save_record(record)

    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")
    assertion = auth.get_assertion(cv.challenge)

    # sign_request takes no "bytes to sign" parameter at all -- it always
    # recomputes from whatever load_record(request_id) returns.
    sv = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(sv.ok, f"sign_request failed: {sv.reason}")
    check(sv.canonical_hash == AR.compute_hash(record), "signed hash did not match the authoritative record")


# --------------------------------------------------------------------------
# no-assertion-no-signature
# --------------------------------------------------------------------------


def test_no_assertion_denial() -> None:
    env = _Env()
    signer = env.signer()
    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))

    sv = signer.sign_request(request_id, None, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv.ok, "sign_request with no assertion produced a signature")
    check(sv.reason == AS.DENY_ASSERTION_MISSING, f"expected assertion-missing, got {sv.reason}")
    check(sv.signature is None, "a denial carried a signature")


def test_no_pending_challenge_denial() -> None:
    """sign_request called without a prior begin_challenge for this
    request_id (even with a structurally well-formed assertion) denies."""
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))
    fake_assertion = auth.get_assertion(os.urandom(32))

    sv = signer.sign_request(request_id, fake_assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv.ok, "sign_request succeeded with no pending challenge")
    check(sv.reason == AS.DENY_NO_PENDING_CHALLENGE, f"expected no-pending-challenge, got {sv.reason}")


# --------------------------------------------------------------------------
# wrong-credential / wrong-challenge
# --------------------------------------------------------------------------


def test_wrong_credential_denial() -> None:
    env = _Env()
    registered = _SoftwareAuthenticator(rp_id=env.rp_id)
    unregistered = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(registered.allowlist_entry())
    signer = env.signer()

    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))
    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")

    assertion = unregistered.get_assertion(cv.challenge)
    sv = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv.ok, "an assertion from an unregistered credential produced a signature")
    check(sv.reason == AS.DENY_UNKNOWN_CREDENTIAL, f"expected unknown-credential, got {sv.reason}")


def test_revoked_credential_denial() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry(status="revoked"))
    signer = env.signer()

    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))
    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")

    assertion = auth.get_assertion(cv.challenge)
    sv = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv.ok, "a revoked credential's assertion produced a signature")
    check(sv.reason == AS.DENY_CREDENTIAL_NOT_ACTIVE, f"expected credential-not-active, got {sv.reason}")


def test_wrong_challenge_denial() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    rid_a, rid_b = _new_request_id(), _new_request_id()
    env.save_record(_fixture_record(rid_a, service="service-a"))
    env.save_record(_fixture_record(rid_b, service="service-b"))

    cv_a = signer.begin_challenge(rid_a, load_record=env.load_record)
    cv_b = signer.begin_challenge(rid_b, load_record=env.load_record)
    check(cv_a.ok and cv_b.ok, "begin_challenge failed for A or B")
    check(cv_a.challenge != cv_b.challenge, "two distinct requests derived the same challenge")

    # An assertion signed over B's challenge, submitted against A's session.
    wrong_assertion = auth.get_assertion(cv_b.challenge)
    sv = signer.sign_request(rid_a, wrong_assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv.ok, "an assertion over a different request's challenge produced a signature")
    check(sv.reason == AS.DENY_ASSERTION_INVALID, f"expected assertion-invalid, got {sv.reason}")


def test_challenge_expired_denial() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer(challenge_ttl=timedelta(seconds=1))

    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    cv = signer.begin_challenge(request_id, load_record=env.load_record, now=t0)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")

    assertion = auth.get_assertion(cv.challenge)
    later = t0 + timedelta(seconds=30)
    sv = signer.sign_request(
        request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes, now=later
    )
    check(not sv.ok, "an expired challenge's assertion produced a signature")
    check(sv.reason == AS.DENY_CHALLENGE_EXPIRED, f"expected challenge-expired, got {sv.reason}")


def test_no_user_verification_denial() -> None:
    """user_verification=required is enforced -- a mere-presence (no
    biometric/PIN) assertion is rejected."""
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id, user_verified=False)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))
    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")

    assertion = auth.get_assertion(cv.challenge, user_verified=False)
    sv = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv.ok, "a non-user-verified assertion produced a signature")
    check(sv.reason == AS.DENY_ASSERTION_INVALID, f"expected assertion-invalid, got {sv.reason}")


def test_clone_suspected_denial() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry(sign_count=10))
    signer = env.signer()

    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))
    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")

    # counter=3 <= stored sign_count=10 -> non-increasing -> clone signal
    assertion = auth.get_assertion(cv.challenge, counter=3)
    sv = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv.ok, "a non-increasing signature counter produced a signature")
    check(sv.reason == AS.DENY_CLONE_SUSPECTED, f"expected sign-count-not-increasing, got {sv.reason}")


# --------------------------------------------------------------------------
# single-use replay — durable across a simulated restart
# --------------------------------------------------------------------------


def test_single_use_replay_durable_across_restart() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))
    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")
    assertion = auth.get_assertion(cv.challenge)

    sv1 = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(sv1.ok, f"first sign_request failed: {sv1.reason}")

    # Second attempt, same signer instance, same (already-consumed) assertion.
    sv2 = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv2.ok, "a replayed sign_request produced a second signature")
    check(
        sv2.reason in (AS.DENY_EXECUTED_REPLAY, AS.DENY_CHALLENGE_REPLAY),
        f"expected a replay denial, got {sv2.reason}",
    )

    # Simulate a process restart: a BRAND NEW ApprovalSigner instance
    # (fresh in-memory guard, fresh Fido2Server) pointed at the SAME
    # on-disk ledger directories must still see the burn -- durability is
    # a filesystem property here, not process memory.
    restarted_signer = env.signer()
    sv3 = restarted_signer.sign_request(
        request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes
    )
    check(not sv3.ok, "a replay was accepted by a freshly-instantiated signer after a simulated restart")
    check(
        sv3.reason in (AS.DENY_EXECUTED_REPLAY, AS.DENY_CHALLENGE_REPLAY),
        f"expected a replay denial after restart, got {sv3.reason}",
    )

    # begin_challenge also refuses to issue a new challenge for an
    # already-signed request_id (defense in depth).
    cv2 = restarted_signer.begin_challenge(request_id, load_record=env.load_record)
    check(not cv2.ok, "begin_challenge issued a fresh challenge for an already-executed request_id")
    check(
        cv2.reason in (AS.DENY_EXECUTED_REPLAY, AS.DENY_CHALLENGE_REPLAY),
        f"expected a replay denial from begin_challenge, got {cv2.reason}",
    )


def test_executed_id_replay_aborts_before_verify() -> None:
    """A re-submitted already-executed request_id aborts BEFORE any
    assertion verification is even attempted -- proven here by replaying
    with assertion=None (which would normally hit DENY_ASSERTION_MISSING)
    and confirming the replay denial wins instead, i.e. the ledger check
    really does run first."""
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    request_id = _new_request_id()
    env.save_record(_fixture_record(request_id))
    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    assertion = auth.get_assertion(cv.challenge)
    sv1 = signer.sign_request(request_id, assertion, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(sv1.ok, f"first sign_request failed: {sv1.reason}")

    sv2 = signer.sign_request(request_id, None, load_record=env.load_record, owner_key=env.owner_key_bytes)
    check(not sv2.ok, "replay with no assertion produced a signature")
    check(
        sv2.reason != AS.DENY_ASSERTION_MISSING,
        "replay of an executed request_id fell through to the assertion-missing check "
        "instead of aborting on the ledger check first",
    )
    check(
        sv2.reason in (AS.DENY_EXECUTED_REPLAY, AS.DENY_CHALLENGE_REPLAY),
        f"expected a replay denial, got {sv2.reason}",
    )


# --------------------------------------------------------------------------
# tamper-abort
# --------------------------------------------------------------------------


def test_tamper_abort() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    request_id = _new_request_id()
    record = _fixture_record(request_id)
    env.save_record(record)
    cv = signer.begin_challenge(request_id, load_record=env.load_record)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")

    # Corrupt the stored canonical_hash (bit flip) -- content unchanged,
    # so validate() still passes; only compute_hash(record) now disagrees.
    good_hash = record["binding"]["canonical_hash"]
    record["binding"]["canonical_hash"] = ("0" if good_hash[0] != "0" else "1") + good_hash[1:]
    check(AR.validate(record).ok, "test setup error: tampered-hash record should still validate() structurally")

    # A structurally well-formed assertion (over an unrelated challenge is
    # fine -- the hash-drift check must abort BEFORE the assertion is ever
    # verified against the real challenge).
    garbage_assertion = auth.get_assertion(os.urandom(32))
    sv = signer.sign_request(
        request_id, garbage_assertion, load_record=env.load_record, owner_key=env.owner_key_bytes
    )
    check(not sv.ok, "a tampered canonical_hash record was signed")
    check(sv.reason == AS.DENY_HASH_DRIFT, f"expected canonical-hash-drift, got {sv.reason}")
    check(sv.signature is None, "a tamper-abort denial carried a signature")


# --------------------------------------------------------------------------
# content-identical-different-request_id -> different signatures
# (finding-2 regression at the signer level)
# --------------------------------------------------------------------------


def test_content_identical_different_request_id_different_signatures() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    rid_a, rid_b = _new_request_id(), _new_request_id()
    record_a = _fixture_record(rid_a, service="identical-service")
    record_b = _fixture_record(rid_b, service="identical-service")
    check(
        record_a["summary"] == record_b["summary"] and record_a["action_manifest"] == record_b["action_manifest"],
        "test setup error: fixture content is not actually identical",
    )
    check(AR.compute_hash(record_a) != AR.compute_hash(record_b), "content-identical records share a canonical_hash")
    env.save_record(record_a)
    env.save_record(record_b)

    cv_a = signer.begin_challenge(rid_a, load_record=env.load_record)
    sv_a = signer.sign_request(
        rid_a, auth.get_assertion(cv_a.challenge), load_record=env.load_record, owner_key=env.owner_key_bytes
    )
    check(sv_a.ok, f"sign A failed: {sv_a.reason}")

    cv_b = signer.begin_challenge(rid_b, load_record=env.load_record)
    sv_b = signer.sign_request(
        rid_b, auth.get_assertion(cv_b.challenge), load_record=env.load_record, owner_key=env.owner_key_bytes
    )
    check(sv_b.ok, f"sign B failed: {sv_b.reason}")

    check(sv_a.signature != sv_b.signature, "content-identical sibling requests produced the SAME signature")

    # And a signature minted for A is not accepted as authorization for B.
    auth_for_b = AS.verify_execution_authorization(record_b, sv_a.signature, env.owner_public_bytes)
    check(not auth_for_b.ok, "A's signature was accepted as authorization for content-identical sibling B")


# --------------------------------------------------------------------------
# verify_execution_authorization — status is NOT the authorization signal
# --------------------------------------------------------------------------


def test_verify_execution_authorization() -> None:
    env = _Env()
    request_id = _new_request_id()
    record = _fixture_record(request_id)
    canonical_hash = AR.compute_hash(record)
    valid_sig = env.owner_private.sign(AS._signable_bytes(canonical_hash)).hex()

    ok_verdict = AS.verify_execution_authorization(record, valid_sig, env.owner_public_bytes)
    check(ok_verdict.ok, f"a valid owner signature was rejected: {ok_verdict.reason}")
    check(ok_verdict.reason == AS.AUTH_OK, f"expected AUTH_OK, got {ok_verdict.reason}")

    wrong_key = Ed25519PrivateKey.generate()
    wrong_sig = wrong_key.sign(AS._signable_bytes(canonical_hash)).hex()
    bad_verdict = AS.verify_execution_authorization(record, wrong_sig, env.owner_public_bytes)
    check(not bad_verdict.ok, "a signature from the wrong key was accepted")
    check(bad_verdict.reason == AS.AUTH_DENY_BAD_SIGNATURE, f"expected bad-signature, got {bad_verdict.reason}")

    # status is NOT the authorization signal: a legal status transition
    # (which never touches canonical_hash) does not affect the verdict.
    approved, _ = AR.transition(record, AR.STATUS_APPROVED, actor="test")
    still_ok = AS.verify_execution_authorization(approved, valid_sig, env.owner_public_bytes)
    check(still_ok.ok, "verify_execution_authorization is sensitive to `status` -- it must not be")

    malformed_record = AS.verify_execution_authorization("not-a-record", valid_sig, env.owner_public_bytes)
    check(not malformed_record.ok and malformed_record.reason == AS.AUTH_DENY_RECORD_MALFORMED, "malformed record was accepted")

    malformed_sig = AS.verify_execution_authorization(record, "not-hex!!", env.owner_public_bytes)
    check(not malformed_sig.ok and malformed_sig.reason == AS.AUTH_DENY_SIGNATURE_MALFORMED, "malformed signature was accepted")

    malformed_key = AS.verify_execution_authorization(record, valid_sig, b"too-short")
    check(not malformed_key.ok and malformed_key.reason == AS.AUTH_DENY_KEY_MALFORMED, "malformed owner key was accepted")


# --------------------------------------------------------------------------
# rate-limit / max-concurrent-session guard (Antigravity hardening 3)
# --------------------------------------------------------------------------


def test_signing_session_guard_concurrency_and_rate_limit() -> None:
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    guard = AS.SigningSessionGuard(
        max_concurrent=1, rate_limit_window=timedelta(seconds=60), rate_limit_max=2
    )

    # Attempt 1 (successful): consumes one rate-limit slot.
    v1 = guard.try_begin(now=t0)
    check(v1.ok, "first session was refused")

    # A concurrent second attempt while v1's slot is still held is refused
    # for CONCURRENCY, not rate -- and must NOT itself consume a rate slot.
    v2 = guard.try_begin(now=t0)
    check(not v2.ok and v2.reason == AS.DENY_CONCURRENT_SESSION, f"a second concurrent session was allowed: {v2}")
    guard.end()  # release v1's slot

    # Attempt 2 (successful): the second and last rate-limit slot in this window.
    v3 = guard.try_begin(now=t0 + timedelta(seconds=1))
    check(v3.ok, "second begin within the rate window was refused unexpectedly")
    guard.end()

    # Attempt 3 within the SAME window: rate_limit_max=2 already spent by
    # attempts 1 and 2 above, so this MUST be rate-limited.
    v4 = guard.try_begin(now=t0 + timedelta(seconds=2))
    check(not v4.ok and v4.reason == AS.DENY_RATE_LIMITED, f"rate limit did not trigger on the 3rd attempt: {v4}")

    # Outside the window, the rate limiter resets.
    v5 = guard.try_begin(now=t0 + timedelta(seconds=120))
    check(v5.ok, "rate limiter did not reset outside its window")


def test_approval_signer_honors_concurrency_guard() -> None:
    env = _Env()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer(max_concurrent_sessions=1, rate_limit_max=1000)

    rid_a, rid_b = _new_request_id(), _new_request_id()
    env.save_record(_fixture_record(rid_a))
    env.save_record(_fixture_record(rid_b))

    cv_a = signer.begin_challenge(rid_a, load_record=env.load_record)
    check(cv_a.ok, f"begin_challenge A failed: {cv_a.reason}")

    cv_b = signer.begin_challenge(rid_b, load_record=env.load_record)
    check(not cv_b.ok, "a second concurrent begin_challenge was allowed under max_concurrent_sessions=1")
    check(cv_b.reason == AS.DENY_CONCURRENT_SESSION, f"expected concurrent-session-active, got {cv_b.reason}")

    # Completing A's session (success or failure) releases the slot.
    sv_a = signer.sign_request(
        rid_a, auth.get_assertion(cv_a.challenge), load_record=env.load_record, owner_key=env.owner_key_bytes
    )
    check(sv_a.ok, f"sign_request A failed: {sv_a.reason}")

    cv_b_retry = signer.begin_challenge(rid_b, load_record=env.load_record)
    check(cv_b_retry.ok, f"begin_challenge B still refused after A's session ended: {cv_b_retry.reason}")


# --------------------------------------------------------------------------
# credential allowlist loader
# --------------------------------------------------------------------------


def test_credential_allowlist_loader_fail_closed() -> None:
    check(AS.load_credential_allowlist("/does/not/exist/credentials.json") is None, "missing file did not deny")

    with tempfile.TemporaryDirectory() as d:
        bad_json = Path(d) / "bad.json"
        bad_json.write_text("not json", encoding="utf-8")
        check(AS.load_credential_allowlist(bad_json) is None, "malformed JSON was accepted")

        wrong_schema = Path(d) / "wrong-schema.json"
        wrong_schema.write_text(json.dumps({"schema_version": "99", "revision": 1, "credentials": []}), encoding="utf-8")
        check(AS.load_credential_allowlist(wrong_schema) is None, "wrong schema_version was accepted")

        bad_hex = Path(d) / "bad-hex.json"
        bad_hex.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "revision": 1,
                    "credentials": [
                        {"credential_id": "zz", "public_key": "00" * 32, "sign_count": 0, "status": "active"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        check(AS.load_credential_allowlist(bad_hex) is None, "non-hex credential_id was accepted")

        good = Path(d) / "good.json"
        good.write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "revision": 1,
                    "credentials": [
                        {"credential_id": "aa", "public_key": "11" * 32, "sign_count": 0, "status": "active"}
                    ],
                }
            ),
            encoding="utf-8",
        )
        loaded = AS.load_credential_allowlist(good)
        check(loaded is not None and "aa" in loaded, "a well-formed allowlist failed to load")


# --------------------------------------------------------------------------
# Antigravity hardening 4 — no software authenticator in the production
# module, no import, no runtime flag.
# --------------------------------------------------------------------------


def test_production_module_excludes_software_authenticator() -> None:
    # Check actual import statements, not bare substrings -- this module's
    # own docstring legitimately DISCUSSES `fido2.mock` in prose (documenting
    # that it is excluded), which would false-positive a naive substring scan.
    for banned_import in ("import fido2.mock", "from fido2.mock", "from fido2 import mock"):
        check(banned_import not in APPROVAL_SIGNER_SOURCE, f"approval_signer.py contains {banned_import!r}")
    check(
        "SoftwareAuthenticator" not in APPROVAL_SIGNER_SOURCE,
        "approval_signer.py references a software/virtual authenticator class",
    )
    check(
        not hasattr(AS, "_SoftwareAuthenticator") and not hasattr(AS, "SoftwareAuthenticator"),
        "approval_signer module exposes a software-authenticator symbol",
    )

    # The load-bearing checks: approval_signer.py must never CONSTRUCT an
    # assertion (that is forging one, the software authenticator's job) --
    # it only ever CONSUMES a caller-supplied `assertion` and verifies it
    # via `isinstance(assertion, w.AuthenticationResponse)` + the real
    # `Fido2Server`. These substrings are the concrete Python constructs a
    # software/virtual authenticator would need; their absence here is the
    # actual, code-level (not prose-level) proof of hardening 4 -- a bare
    # substring check on words like "virtual" would false-positive on this
    # module's own documentation of what it deliberately excludes.
    for forging_construct in (
        "AuthenticatorAssertionResponse(",  # builds a fake assertion payload
        "CollectedClientData.create(",  # builds fake clientDataJSON
        "Ed25519PrivateKey.generate()",  # mints a fresh (fake) credential keypair
    ):
        check(
            forging_construct not in APPROVAL_SIGNER_SOURCE,
            f"approval_signer.py contains {forging_construct!r} -- an assertion-forging construct",
        )


def main() -> int:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_") and callable(value)]
    failures = []
    for test in tests:
        try:
            test()
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{test.__name__}: {exc}")
    if failures:
        print(f"FAIL ({len(failures)}):")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    print(f"PASS: {len(tests)} approval-signer P1 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
