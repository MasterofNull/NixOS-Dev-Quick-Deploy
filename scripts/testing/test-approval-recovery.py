#!/usr/bin/env python3
"""Acceptance tests for the Approval Control Plane P1b lost-authenticator
recovery CORE (`scripts/ai/lib/approval_recovery.py`).

Covers the "Validation goals" from
`.agents/plans/approval-control-plane/ACP-P1b-DESIGN-20260816.md`:
backup-works, lose-one-safe, console-only-recovery, no-empty-allowlist,
audited, no-stored-secret. `test_backup_works` and `test_lose_one_safe` go
one step further than "allowlist level" alone: they also run a REAL P1
`approval_signer.ApprovalSigner` (real `python-fido2` verification, no
mocks) against a credential enrolled through this module's
`AllowlistManager`, proving the P1b-managed allowlist file is genuinely
consumable by P1 unmodified -- not just structurally plausible.

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

import approval_recovery as ARC  # noqa: E402
import approval_request as AR  # noqa: E402
import approval_signer as AS  # noqa: E402

APPROVAL_RECOVERY_SOURCE = (LIB_DIR / "approval_recovery.py").read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# --------------------------------------------------------------------------
# TEST-ONLY software/virtual WebAuthn authenticator -- same idiom as
# `test-approval-signer.py`'s `_SoftwareAuthenticator`, kept local to this
# file rather than imported cross-file (each test file owns its own
# test-only crypto stand-in; never imported by production code).
# --------------------------------------------------------------------------


class _SoftwareAuthenticator:
    def __init__(self, *, rp_id: str, credential_id: bytes = None, user_verified: bool = True) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        self.credential_id = credential_id or os.urandom(32)
        self.rp_id = rp_id
        self.user_verified = user_verified

    @property
    def public_key_hex(self) -> str:
        return self.private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

    def get_assertion(self, challenge: bytes, *, counter: int = 1) -> w.AuthenticationResponse:
        rp_id_hash = hashlib.sha256(self.rp_id.encode("utf-8")).digest()
        flags = w.AuthenticatorData.FLAG.UP
        if self.user_verified:
            flags = flags | w.AuthenticatorData.FLAG.UV
        auth_data = w.AuthenticatorData.create(rp_id_hash, flags, counter)
        client_data = w.CollectedClientData.create(
            type="webauthn.get", challenge=challenge, origin=f"https://{self.rp_id}"
        )
        signature = self.private_key.sign(bytes(auth_data) + client_data.hash)
        response = w.AuthenticatorAssertionResponse(
            client_data=client_data, authenticator_data=auth_data, signature=signature
        )
        return w.AuthenticationResponse(raw_id=self.credential_id, response=response)


def _new_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


class _Env:
    """Fresh temp-dir-backed allowlist/audit-log/ledgers + a throwaway
    owner Ed25519 keypair per test."""

    def __init__(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._base = Path(self.tmp.name)
        self.allowlist_path = self._base / "credentials.json"
        self.audit_log_path = self._base / "audit.jsonl"
        self.challenge_store_dir = self._base / "pending"
        self.challenge_ledger_dir = self._base / "challenge-ledger"
        self.executed_ledger_dir = self._base / "executed-ledger"
        self.rp_id = "approval-recovery.test"

        self.owner_private = Ed25519PrivateKey.generate()
        self.owner_key_bytes = self.owner_private.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        self.owner_public_bytes = self.owner_private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)

    def tmp_path(self, name: str) -> Path:
        return self._base / name

    def manager(self, *, allowlist_path=None, audit_log_path=None) -> ARC.AllowlistManager:
        return ARC.AllowlistManager(
            allowlist_path=allowlist_path or self.allowlist_path,
            audit_log_path=audit_log_path or self.audit_log_path,
        )

    def signer(self) -> AS.ApprovalSigner:
        return AS.ApprovalSigner(
            credential_allowlist_path=self.allowlist_path,
            challenge_store_dir=self.challenge_store_dir,
            challenge_ledger_dir=self.challenge_ledger_dir,
            executed_ledger_dir=self.executed_ledger_dir,
            rp_id=self.rp_id,
            max_concurrent_sessions=8,
            rate_limit_max=1000,
        )

    def make_record(self, service: str = "test-service") -> dict:
        request_id = _new_request_id()
        record = AR.create_request(
            request_id=request_id, created_by="test-suite", runbook="restart-service", params={"service": service}
        )
        return record


# --------------------------------------------------------------------------
# backup-works
# --------------------------------------------------------------------------


def test_backup_works() -> None:
    env = _Env()
    primary = _SoftwareAuthenticator(rp_id=env.rp_id)
    backup = _SoftwareAuthenticator(rp_id=env.rp_id)
    mgr = env.manager()

    v1 = mgr.enroll(
        credential_id=primary.credential_id.hex(),
        public_key=primary.public_key_hex,
        label="Home Key",
        kind=ARC.KIND_PRIMARY,
        actor="owner",
    )
    check(v1.ok, f"primary enroll failed: {v1.reason} {v1.detail}")
    v2 = mgr.enroll(
        credential_id=backup.credential_id.hex(),
        public_key=backup.public_key_hex,
        label="Backup Key",
        kind=ARC.KIND_BACKUP,
        actor="owner",
    )
    check(v2.ok, f"backup enroll failed: {v2.reason} {v2.detail}")

    # Allowlist level: P1's OWN loader accepts the P1b-managed file, both
    # entries present and active, with P1's exact 4-key entry shape.
    loaded = AS.load_credential_allowlist(env.allowlist_path)
    check(loaded is not None, "P1 loader rejected the P1b-managed allowlist file")
    check(len(loaded) == 2, f"expected 2 loaded credentials, got {len(loaded)}")
    for auth in (primary, backup):
        entry = loaded.get(auth.credential_id.hex())
        check(entry is not None, "credential missing from P1-loaded allowlist")
        check(set(entry.keys()) == AS.CREDENTIAL_KEYS, f"entry has non-P1 keys: {entry.keys()}")
        check(entry["status"] == AS.CREDENTIAL_STATUS_ACTIVE, "enrolled credential not active")

    # End-to-end: a REAL P1 signer accepts an assertion from the BACKUP
    # credential identically to how it would accept the primary's.
    signer = env.signer()
    record = env.make_record()
    store = {record["request_id"]: record}
    cv = signer.begin_challenge(record["request_id"], load_record=store.get)
    check(cv.ok, f"begin_challenge failed: {cv.reason} {cv.detail}")
    assertion = backup.get_assertion(cv.challenge)
    sv = signer.sign_request(record["request_id"], assertion, load_record=store.get, owner_key=env.owner_key_bytes)
    check(sv.ok, f"backup-credential sign_request failed: {sv.reason} {sv.detail}")
    auth_verdict = AS.verify_execution_authorization(record, sv.signature, env.owner_public_bytes)
    check(auth_verdict.ok, f"backup-signed request failed executor-side authorization: {auth_verdict.reason}")

    # list_credentials() projects the label/kind bookkeeping P1 never sees.
    listed = {c["credential_id"]: c for c in mgr.list_credentials()}
    check(listed[primary.credential_id.hex()]["label"] == "Home Key", "primary label not projected")
    check(listed[backup.credential_id.hex()]["kind"] == ARC.KIND_BACKUP, "backup kind not projected")


# --------------------------------------------------------------------------
# lose-one-safe
# --------------------------------------------------------------------------


def test_lose_one_safe() -> None:
    env = _Env()
    primary = _SoftwareAuthenticator(rp_id=env.rp_id)
    backup = _SoftwareAuthenticator(rp_id=env.rp_id)
    mgr = env.manager()
    mgr.enroll(
        credential_id=primary.credential_id.hex(),
        public_key=primary.public_key_hex,
        label="Primary",
        kind=ARC.KIND_PRIMARY,
        actor="owner",
    )
    mgr.enroll(
        credential_id=backup.credential_id.hex(),
        public_key=backup.public_key_hex,
        label="Backup",
        kind=ARC.KIND_BACKUP,
        actor="owner",
    )

    v = mgr.set_status(primary.credential_id.hex(), "revoked", actor="owner")
    check(v.ok, f"disabling primary with an active backup present was refused: {v.reason}")

    loaded = AS.load_credential_allowlist(env.allowlist_path)
    check(loaded[primary.credential_id.hex()]["status"] == "revoked", "primary not marked revoked")
    check(loaded[backup.credential_id.hex()]["status"] == AS.CREDENTIAL_STATUS_ACTIVE, "backup no longer active")

    # The backup still signs fine -- no lockout.
    signer = env.signer()
    record = env.make_record()
    store = {record["request_id"]: record}
    cv = signer.begin_challenge(record["request_id"], load_record=store.get)
    check(cv.ok, f"begin_challenge failed after primary disabled: {cv.reason}")
    assertion = backup.get_assertion(cv.challenge)
    sv = signer.sign_request(record["request_id"], assertion, load_record=store.get, owner_key=env.owner_key_bytes)
    check(sv.ok, f"backup sign_request failed after primary disabled: {sv.reason} {sv.detail}")

    # And the (now revoked) primary is correctly rejected if tried.
    record2 = env.make_record(service="second")
    store[record2["request_id"]] = record2
    cv2 = signer.begin_challenge(record2["request_id"], load_record=store.get)
    check(cv2.ok, f"begin_challenge failed: {cv2.reason}")
    bad_assertion = primary.get_assertion(cv2.challenge)
    sv2 = signer.sign_request(
        record2["request_id"], bad_assertion, load_record=store.get, owner_key=env.owner_key_bytes
    )
    check(not sv2.ok, "a revoked primary's assertion still produced a signature")
    check(sv2.reason == AS.DENY_CREDENTIAL_NOT_ACTIVE, f"expected credential-not-active, got {sv2.reason}")


# --------------------------------------------------------------------------
# no-empty-allowlist
# --------------------------------------------------------------------------


def test_no_empty_allowlist() -> None:
    env = _Env()
    only = _SoftwareAuthenticator(rp_id=env.rp_id)
    mgr = env.manager()
    v = mgr.enroll(
        credential_id=only.credential_id.hex(),
        public_key=only.public_key_hex,
        label="Only Key",
        kind=ARC.KIND_PRIMARY,
        actor="owner",
    )
    check(v.ok, f"enroll failed: {v.reason}")

    # Disabling the only active credential is refused.
    v_disable = mgr.set_status(only.credential_id.hex(), "revoked", actor="owner")
    check(not v_disable.ok, "disabling the last active credential succeeded -- self-lockout")
    check(
        v_disable.reason == ARC.DENY_LAST_ACTIVE_CREDENTIAL,
        f"expected last-active-credential, got {v_disable.reason}",
    )
    loaded = AS.load_credential_allowlist(env.allowlist_path)
    check(
        loaded[only.credential_id.hex()]["status"] == AS.CREDENTIAL_STATUS_ACTIVE,
        "credential status mutated despite refusal (fail-open)",
    )

    # Removing the only credential outright is also refused.
    v_remove = mgr.remove(only.credential_id.hex(), actor="owner")
    check(not v_remove.ok, "removing the last active credential succeeded -- fail-open empty allowlist")
    check(
        v_remove.reason == ARC.DENY_LAST_ACTIVE_CREDENTIAL,
        f"expected last-active-credential, got {v_remove.reason}",
    )
    loaded2 = AS.load_credential_allowlist(env.allowlist_path)
    check(only.credential_id.hex() in loaded2, "credential removed from allowlist despite refusal")

    # ...but removal WITH an atomic replacement succeeds.
    replacement = _SoftwareAuthenticator(rp_id=env.rp_id)
    v_ok = mgr.remove(
        only.credential_id.hex(),
        actor="owner",
        replacement={
            "credential_id": replacement.credential_id.hex(),
            "public_key": replacement.public_key_hex,
            "label": "Replacement Key",
            "kind": ARC.KIND_BACKUP,
        },
    )
    check(v_ok.ok, f"remove-with-replacement was refused: {v_ok.reason} {v_ok.detail}")
    loaded3 = AS.load_credential_allowlist(env.allowlist_path)
    check(only.credential_id.hex() not in loaded3, "old credential still present after replaced removal")
    check(replacement.credential_id.hex() in loaded3, "replacement credential missing after replaced removal")
    check(len(loaded3) == 1, f"unexpected credential count after replaced removal: {len(loaded3)}")

    # Now that single (replacement) credential is again the "last active" --
    # disabling it without a replacement is refused too (invariant holds
    # after mutation, not just at t=0).
    v_disable2 = mgr.set_status(replacement.credential_id.hex(), "revoked", actor="owner")
    check(not v_disable2.ok, "disabling the new last-active credential succeeded -- self-lockout")


# --------------------------------------------------------------------------
# console-only-recovery
# --------------------------------------------------------------------------


def test_console_only_recovery() -> None:
    env = _Env()
    mgr = env.manager()
    fresh = _SoftwareAuthenticator(rp_id=env.rp_id)
    expected_token = "s3cr3t-console-presence-token"  # noqa: S105 - test fixture, not a real secret

    # An agent connected over the UDS: not euid 0, even if it somehow knew
    # the token.
    v_agent = mgr.bootstrap_recovery(
        credential_id=fresh.credential_id.hex(),
        public_key=fresh.public_key_hex,
        label="Recovery Key",
        euid=1000,
        console_presence_token=expected_token,
        expected_console_presence_token=expected_token,
        actor="agent-over-uds",
    )
    check(not v_agent.ok, "a non-root (UDS-agent-simulated) caller enrolled a recovery credential")
    check(v_agent.reason == ARC.DENY_EUID_NOT_ROOT, f"expected euid-not-root, got {v_agent.reason}")

    # Root euid but a mismatched/forged presence token.
    v_forged = mgr.bootstrap_recovery(
        credential_id=fresh.credential_id.hex(),
        public_key=fresh.public_key_hex,
        label="Recovery Key",
        euid=0,
        console_presence_token="guessed-token",
        expected_console_presence_token=expected_token,
        actor="root-no-console",
    )
    check(not v_forged.ok, "root euid with a mismatched presence token enrolled a recovery credential")
    check(
        v_forged.reason == ARC.DENY_CONSOLE_TOKEN_MISMATCH, f"expected console-token-mismatch, got {v_forged.reason}"
    )

    # Root euid but the expected token is missing/unconfigured -- fail
    # CLOSED, not silently "no check needed".
    v_misconfig = mgr.bootstrap_recovery(
        credential_id=fresh.credential_id.hex(),
        public_key=fresh.public_key_hex,
        label="Recovery Key",
        euid=0,
        console_presence_token="anything",
        expected_console_presence_token=None,
        actor="root-misconfigured",
    )
    check(not v_misconfig.ok, "a misconfigured (missing expected token) recovery gate fail-opened")
    check(
        v_misconfig.reason == ARC.DENY_CONSOLE_TOKEN_MISCONFIGURED,
        f"expected console-token-misconfigured, got {v_misconfig.reason}",
    )

    # None of the refused attempts wrote anything.
    check(AS.load_credential_allowlist(env.allowlist_path) is None, "a refused recovery attempt still wrote a credential")

    # Genuine console-root presence: succeeds.
    v_real = mgr.bootstrap_recovery(
        credential_id=fresh.credential_id.hex(),
        public_key=fresh.public_key_hex,
        label="Recovery Key",
        euid=0,
        console_presence_token=expected_token,
        expected_console_presence_token=expected_token,
        actor="owner-console",
    )
    check(v_real.ok, f"genuine console-root recovery was refused: {v_real.reason} {v_real.detail}")
    loaded = AS.load_credential_allowlist(env.allowlist_path)
    check(fresh.credential_id.hex() in loaded, "recovery-enrolled credential missing from allowlist")

    # Recovery structurally cannot carry a signature/authorization.
    check(not hasattr(v_real, "signature"), "recovery verdict exposes a signature field")
    check("signature" not in ARC.MutationVerdict.__dataclass_fields__, "MutationVerdict can carry a signature field")


# --------------------------------------------------------------------------
# audited
# --------------------------------------------------------------------------


def test_audited() -> None:
    env = _Env()
    mgr = env.manager()
    a = _SoftwareAuthenticator(rp_id=env.rp_id)
    b = _SoftwareAuthenticator(rp_id=env.rp_id)

    mgr.enroll(credential_id=a.credential_id.hex(), public_key=a.public_key_hex, label="A", kind=ARC.KIND_PRIMARY, actor="owner")
    mgr.enroll(credential_id=b.credential_id.hex(), public_key=b.public_key_hex, label="B", kind=ARC.KIND_BACKUP, actor="owner")
    mgr.set_status(a.credential_id.hex(), "revoked", actor="owner")

    events = mgr.audit_events()
    kinds = [e.get("event") for e in events]
    check(kinds.count(ARC.AUDIT_EVENT_ENROLLED) == 2, f"expected 2 enroll events, got {kinds}")
    check(ARC.AUDIT_EVENT_STATUS_CHANGED in kinds, f"expected a status-change event, got {kinds}")
    for e in events:
        for required_field in ("event", "credential_id", "actor", "at"):
            check(required_field in e, f"audit event missing {required_field!r}: {e}")

    # A refused mutation must NOT emit a fresh event (no-empty-allowlist
    # refusal on the now-last-active B).
    count_before = len(mgr.audit_events())
    refusal = mgr.set_status(b.credential_id.hex(), "revoked", actor="owner")
    check(not refusal.ok, "test setup error: expected this to be refused (last active credential)")
    check(len(mgr.audit_events()) == count_before, "a refused mutation still appended an audit event")

    # Console-gated recovery emits its own distinguishable event type.
    fresh = _SoftwareAuthenticator(rp_id=env.rp_id)
    v = mgr.bootstrap_recovery(
        credential_id=fresh.credential_id.hex(),
        public_key=fresh.public_key_hex,
        label="Recovery",
        euid=0,
        console_presence_token="tok",
        expected_console_presence_token="tok",
        actor="owner-console",
    )
    check(v.ok, f"recovery bootstrap failed: {v.reason}")
    events2 = mgr.audit_events()
    check(
        any(e.get("event") == ARC.AUDIT_EVENT_RECOVERY_BOOTSTRAP for e in events2),
        "recovery enrollment was not audited with its own distinct event type",
    )

    # Durable across a fresh AuditLog instance pointed at the same path
    # (same durability property `test_single_use_replay_durable_across_restart`
    # exercises for P1's ledgers).
    reread = ARC.AuditLog(env.audit_log_path).read_all()
    check(len(reread) == len(events2), "audit log did not survive a fresh reader instance")


# --------------------------------------------------------------------------
# no-stored-secret
# --------------------------------------------------------------------------


def test_no_stored_secret() -> None:
    banned_substrings = [
        "recovery_code",
        "recoverycode",
        "break_glass",
        "breakglass",
        "backdoor",
        "smtplib",
        "twilio",
        "sendgrid",
    ]
    for banned in banned_substrings:
        check(banned not in APPROVAL_RECOVERY_SOURCE, f"approval_recovery.py contains {banned!r}")

    # No PRIVATE key material anywhere -- checked as actual Python
    # constructs (an import, an instantiation, a signing call), not a bare
    # substring, since this module's own docstring legitimately DISCUSSES
    # "Ed25519PrivateKey" in prose to document that it is excluded (same
    # false-positive risk `test-approval-signer.py`'s
    # `test_production_module_excludes_software_authenticator` guards
    # against for `fido2.mock`).
    for forging_construct in (
        "import Ed25519PrivateKey",
        "Ed25519PrivateKey(",
        "Ed25519PrivateKey.generate(",
        "Ed25519PrivateKey.from_private_bytes(",
        ".sign(",
    ):
        check(
            forging_construct not in APPROVAL_RECOVERY_SOURCE,
            f"approval_recovery.py contains {forging_construct!r} -- private-key/signing construct",
        )

    # No function/attribute anywhere on the module or AllowlistManager
    # exposes anything code/secret-shaped.
    suspicious_name_fragments = ("code", "secret", "sms", "email")
    for name in dir(ARC):
        lowered = name.lower()
        if any(frag in lowered for frag in suspicious_name_fragments):
            raise AssertionError(f"approval_recovery module exposes a suspicious top-level name: {name!r}")
    for name in dir(ARC.AllowlistManager):
        if name.startswith("_"):
            continue
        lowered = name.lower()
        if any(frag in lowered for frag in suspicious_name_fragments):
            raise AssertionError(f"AllowlistManager exposes a suspicious method/attribute: {name!r}")

    # Structural: MutationVerdict (the return type of every mutation,
    # including recovery) has no signature/secret-shaped field.
    for field_name in ARC.MutationVerdict.__dataclass_fields__:
        lowered = field_name.lower()
        check(
            not any(frag in lowered for frag in ("signature", "secret", "code", "key")),
            f"MutationVerdict has a secret/signature-shaped field: {field_name!r}",
        )


# --------------------------------------------------------------------------
# Field validation / fail-closed plumbing (supporting coverage, not a named
# design validation goal but load-bearing for the goals above).
# --------------------------------------------------------------------------


def test_enroll_rejects_invalid_fields() -> None:
    env = _Env()
    mgr = env.manager()
    good_key = _SoftwareAuthenticator(rp_id=env.rp_id).public_key_hex

    v_bad_id = mgr.enroll(credential_id="not-hex!!", public_key=good_key, label="X", actor="owner")
    check(not v_bad_id.ok and v_bad_id.reason == ARC.DENY_INVALID_CREDENTIAL_ID, f"bad credential_id accepted: {v_bad_id}")

    v_bad_key = mgr.enroll(credential_id="aa", public_key="zz", label="X", actor="owner")
    check(not v_bad_key.ok and v_bad_key.reason == ARC.DENY_INVALID_PUBLIC_KEY, f"bad public_key accepted: {v_bad_key}")

    v_bad_label = mgr.enroll(credential_id="aa", public_key=good_key, label="", actor="owner")
    check(not v_bad_label.ok and v_bad_label.reason == ARC.DENY_INVALID_LABEL, f"empty label accepted: {v_bad_label}")

    v_bad_kind = mgr.enroll(credential_id="aa", public_key=good_key, label="X", kind="admin", actor="owner")
    check(not v_bad_kind.ok and v_bad_kind.reason == ARC.DENY_INVALID_KIND, f"bad kind accepted: {v_bad_kind}")

    # Nothing was written by any of the above.
    check(AS.load_credential_allowlist(env.allowlist_path) is None, "an invalid enroll attempt still wrote a file")


def test_duplicate_credential_rejected() -> None:
    env = _Env()
    mgr = env.manager()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    v1 = mgr.enroll(credential_id=auth.credential_id.hex(), public_key=auth.public_key_hex, label="A", actor="owner")
    check(v1.ok, f"first enroll failed: {v1.reason}")
    v2 = mgr.enroll(credential_id=auth.credential_id.hex(), public_key=auth.public_key_hex, label="A again", actor="owner")
    check(not v2.ok and v2.reason == ARC.DENY_DUPLICATE_CREDENTIAL, f"duplicate credential_id accepted: {v2}")


def test_unreadable_allowlist_fails_closed() -> None:
    env = _Env()
    env.allowlist_path.parent.mkdir(parents=True, exist_ok=True)
    env.allowlist_path.write_text("not json", encoding="utf-8")
    mgr = env.manager()
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)

    v_enroll = mgr.enroll(credential_id=auth.credential_id.hex(), public_key=auth.public_key_hex, label="X", actor="owner")
    check(not v_enroll.ok and v_enroll.reason == ARC.DENY_ALLOWLIST_UNREADABLE, f"enroll on malformed allowlist succeeded: {v_enroll}")

    v_status = mgr.set_status("aa", "revoked", actor="owner")
    check(not v_status.ok and v_status.reason == ARC.DENY_ALLOWLIST_UNREADABLE, f"set_status on malformed allowlist succeeded: {v_status}")

    v_remove = mgr.remove("aa", actor="owner")
    check(not v_remove.ok and v_remove.reason == ARC.DENY_ALLOWLIST_UNREADABLE, f"remove on malformed allowlist succeeded: {v_remove}")

    check(mgr.list_credentials() is None, "list_credentials did not fail closed on a malformed allowlist")

    # The malformed file was never clobbered by any of the above.
    check(env.allowlist_path.read_text(encoding="utf-8") == "not json", "a refused mutation still touched the malformed file")


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
    print(f"PASS: {len(tests)} approval-recovery P1b checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
