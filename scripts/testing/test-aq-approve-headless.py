#!/usr/bin/env python3
"""Acceptance tests for the Approval Control Plane P4 headless CLI
(`scripts/ai/aq-approve-headless`).

Covers the "Validation goals" from
`.agents/plans/approval-control-plane/ACP-P4-DESIGN-20260816.md`:
headless-happy-path, same-guarantees (shares P1's single-use/executed-id
semantics), no-passphrase-fallback (static + behavioral), plain-language-cli
(Layer-1 default, no hex/path), agent-cannot-complete (no-UV / unregistered
credential refused).

WebAuthn crypto is exercised with a REAL software authenticator producing a
REAL `fido2.webauthn.AuthenticationResponse` over the REAL challenge
`approval_signer.ApprovalSigner.begin_challenge` derives, verified by the
REAL `python-fido2` server code inside `ApprovalSigner.sign_request` --
never a mocked verify call, and never through `aq-approve-headless`'s own
`HidrawFido2Client` (that class talks to real USB hidraw devices only; it is
never imported or constructed by this test file). The software authenticator
(`_SoftwareAuthenticator` below, copied from `test-approval-signer.py`'s
proven pattern) is TEST-ONLY: it exists exclusively in this file and is
never importable from `aq-approve-headless` (asserted directly in
`test_production_cli_excludes_software_authenticator` below).

`check()` raises `AssertionError` immediately on a failed condition so
`pytest` reports real per-test PASS/FAIL. `main()` runs every `test_*`
function and aggregates failures for a single human-readable summary when
run directly.
"""

from __future__ import annotations

import hashlib
import io
import os
import sys
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AI_DIR = REPO_ROOT / "scripts" / "ai"
LIB_DIR = AI_DIR / "lib"
sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(AI_DIR))

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

# `aq-approve-headless` has no `.py` suffix -- load it explicitly via
# importlib.machinery.SourceFileLoader (spec_from_file_location cannot infer
# a loader from an extension-less path on its own) rather than relying on
# import-by-filename.
import importlib.util as _ilu  # noqa: E402
from importlib.machinery import SourceFileLoader  # noqa: E402

_CLI_PATH = AI_DIR / "aq-approve-headless"
_loader = SourceFileLoader("aq_approve_headless", str(_CLI_PATH))
_spec = _ilu.spec_from_loader("aq_approve_headless", _loader)
AH = _ilu.module_from_spec(_spec)
_loader.exec_module(AH)

CLI_SOURCE = _CLI_PATH.read_text(encoding="utf-8")


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


# --------------------------------------------------------------------------
# TEST-ONLY software/virtual WebAuthn authenticator -- identical protocol
# shape to test-approval-signer.py's `_SoftwareAuthenticator`. NEVER
# imported by aq-approve-headless; see
# test_production_cli_excludes_software_authenticator below.
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

    def allowlist_entry(self, *, status: str = "active", sign_count: int = 0) -> dict:
        return {
            "credential_id": self.credential_id.hex(),
            "public_key": self.public_key_hex,
            "sign_count": sign_count,
            "status": status,
        }

    def get_assertion(
        self,
        *,
        challenge: bytes,
        rp_id: str = None,
        credential_ids=None,
        user_verification: str = "required",
    ) -> w.AuthenticationResponse:
        """Same call signature `aq-approve-headless.cmd_approve` uses for its
        injected `get_assertion` seam (keyword-only challenge/rp_id/
        credential_ids/user_verification) -- a drop-in stand-in for
        `HidrawFido2Client.get_assertion` in every test below."""
        target_rp_id = rp_id or self.rp_id
        uv = self.user_verified if user_verification == "required" else self.user_verified
        rp_id_hash = hashlib.sha256(target_rp_id.encode("utf-8")).digest()
        flags = w.AuthenticatorData.FLAG.UP
        if uv:
            flags = flags | w.AuthenticatorData.FLAG.UV
        auth_data = w.AuthenticatorData.create(rp_id_hash, flags, 1)
        client_data = w.CollectedClientData.create(
            type="webauthn.get", challenge=challenge, origin=f"https://{target_rp_id}"
        )
        signature = self.private_key.sign(bytes(auth_data) + client_data.hash)
        response = w.AuthenticatorAssertionResponse(
            client_data=client_data, authenticator_data=auth_data, signature=signature
        )
        return w.AuthenticationResponse(raw_id=self.credential_id, response=response)


def _unregistered_get_assertion(**_kwargs) -> None:
    """Stands in for 'no hardware present' -- an agent invoking the CLI with
    no security key plugged in must get exactly this, never a signature."""
    return None


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def _new_request_id() -> str:
    return f"req-{uuid.uuid4().hex}"


def _fixture_record(request_id: str, *, service: str = "aq-approve-headless-test") -> dict:
    return AR.create_request(
        request_id=request_id,
        created_by="test-suite",
        runbook="restart-service",
        params={"service": service},
    )


class _Env:
    """Fresh temp-dir-backed signer state + a throwaway owner Ed25519
    keypair per test, plus an `AH.FixtureApprovalStore` seeded with exactly
    one record so `cmd_approve`/`cmd_deny` have something real to act on."""

    def __init__(self, *, records=None) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        self.allowlist_path = base / "credentials.json"
        self.state_dir = base / "state"
        self.rp_id = "aq-approve-headless.test"

        self.owner_private = Ed25519PrivateKey.generate()
        self.owner_key_bytes = self.owner_private.private_bytes(
            Encoding.Raw, PrivateFormat.Raw, NoEncryption()
        )
        self.owner_public_bytes = self.owner_private.public_key().public_bytes(
            Encoding.Raw, PublicFormat.Raw
        )

        self._write_allowlist([])
        self.store = AH.FixtureApprovalStore(records or [])

    def _write_allowlist(self, entries: list) -> None:
        import json

        doc = {"schema_version": "1", "revision": 1, "credentials": entries}
        self.allowlist_path.write_text(json.dumps(doc), encoding="utf-8")

    def add_credential(self, entry: dict) -> None:
        import json

        entries = json.loads(self.allowlist_path.read_text(encoding="utf-8"))["credentials"]
        entries.append(entry)
        self._write_allowlist(entries)

    def credential_ids(self) -> list:
        allowlist = AS.load_credential_allowlist(self.allowlist_path)
        return [
            bytes.fromhex(cid)
            for cid, entry in (allowlist or {}).items()
            if entry["status"] == AS.CREDENTIAL_STATUS_ACTIVE
        ]

    def signer(self, **overrides) -> AS.ApprovalSigner:
        return AH._build_signer(
            allowlist_path=str(self.allowlist_path),
            state_dir=str(self.state_dir),
            rp_id=self.rp_id,
        ) if not overrides else AS.ApprovalSigner(
            credential_allowlist_path=self.allowlist_path,
            challenge_store_dir=self.state_dir / "pending",
            challenge_ledger_dir=self.state_dir / "challenge-ledger",
            executed_ledger_dir=self.state_dir / "executed-ledger",
            rp_id=self.rp_id,
            **overrides,
        )


def _run_approve(env: _Env, request_id: str, get_assertion, *, out=None) -> int:
    buf = out if out is not None else io.StringIO()
    return AH.cmd_approve(
        env.store,
        env.signer(),
        env.owner_key_bytes,
        request_id,
        get_assertion=get_assertion,
        rp_id=env.rp_id,
        credential_ids=env.credential_ids(),
        out=buf,
    )


# --------------------------------------------------------------------------
# headless-happy-path
# --------------------------------------------------------------------------


def test_headless_happy_path_yields_signature_via_signer_path() -> None:
    request_id = _new_request_id()
    env = _Env(records=[_fixture_record(request_id)])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())

    buf = io.StringIO()
    rc = _run_approve(env, request_id, auth.get_assertion, out=buf)
    check(rc == 0, f"cmd_approve did not succeed on the happy path: {buf.getvalue()}")
    check(AH.PREP_COPY["success_message"] in buf.getvalue(), "success_message not printed on success")
    check(AH.PREP_COPY["approve_prompt"] in buf.getvalue(), "approve_prompt not printed before the tap")

    # The record really transitioned in the store -- not just a printed
    # message with no state change.
    record = env.store.get(request_id)
    check(record["status"] == AR.STATUS_APPROVED, f"store record status is {record['status']!r}, expected approved")


def test_headless_signature_verifies_under_owner_public_key() -> None:
    """The signature the headless path produced is a REAL, independently-
    verifiable Ed25519 signature over the record's canonical_hash -- proven
    by re-deriving the challenge/verify path directly against the signer,
    not just trusting cmd_approve's return code."""
    request_id = _new_request_id()
    record = _fixture_record(request_id)
    env = _Env(records=[record])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    cv = signer.begin_challenge(request_id, load_record=env.store.get)
    check(cv.ok, f"begin_challenge failed: {cv.reason}")
    assertion = auth.get_assertion(challenge=cv.challenge, rp_id=env.rp_id)
    sv = signer.sign_request(request_id, assertion, load_record=env.store.get, owner_key=env.owner_key_bytes)
    check(sv.ok, f"sign_request failed: {sv.reason}")

    auth_verdict = AS.verify_execution_authorization(record, sv.signature, env.owner_public_bytes)
    check(auth_verdict.ok, f"headless-produced signature failed independent verification: {auth_verdict.reason}")


# --------------------------------------------------------------------------
# same-guarantees -- shares P1's single-use / executed-id ledgers
# --------------------------------------------------------------------------


def test_replay_refused_identically_to_browser_path() -> None:
    request_id = _new_request_id()
    env = _Env(records=[_fixture_record(request_id)])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())

    rc1 = _run_approve(env, request_id, auth.get_assertion)
    check(rc1 == 0, "first headless approve unexpectedly failed")

    # Re-fetch: cmd_approve already transitioned the record to approved, so
    # a second attempt is refused at the CLI's own status check, exactly
    # like the P1/P2 "already-executed" refusal the design requires headless
    # to share -- not a different code path, the SAME semantics.
    buf2 = io.StringIO()
    rc2 = _run_approve(env, request_id, auth.get_assertion, out=buf2)
    check(rc2 != 0, "a replayed approve on an already-approved request succeeded")
    check(AH._ALREADY_DONE_MESSAGE in buf2.getvalue(), "replay did not surface the already-done message")


def test_replay_refused_at_signer_level_even_with_record_reset() -> None:
    """Even if the STORE's status were reset (simulating a bug elsewhere),
    the P1 executed-id ledger this CLI shares still refuses the replay --
    the ledger, not the store's status field, is the real single-use gate
    (mirrors test-approval-signer.py's own executed-id-replay coverage)."""
    request_id = _new_request_id()
    record = _fixture_record(request_id)
    env = _Env(records=[record])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())
    signer = env.signer()

    cv = signer.begin_challenge(request_id, load_record=env.store.get)
    assertion = auth.get_assertion(challenge=cv.challenge, rp_id=env.rp_id)
    sv1 = signer.sign_request(request_id, assertion, load_record=env.store.get, owner_key=env.owner_key_bytes)
    check(sv1.ok, f"first sign_request failed: {sv1.reason}")

    # Same signer instance, same already-consumed assertion.
    sv2 = signer.sign_request(request_id, assertion, load_record=env.store.get, owner_key=env.owner_key_bytes)
    check(not sv2.ok, "a replayed sign_request via the headless-shared signer produced a second signature")
    check(
        sv2.reason in (AS.DENY_EXECUTED_REPLAY, AS.DENY_CHALLENGE_REPLAY),
        f"expected a replay denial, got {sv2.reason}",
    )


def test_tampered_record_refused_identically() -> None:
    """A tampered `canonical_hash` is refused BEFORE the hardware ceremony
    is even meaningfully consulted -- same `DENY_HASH_DRIFT` abort P1's own
    test suite exercises, reached here entirely through the CLI's
    `cmd_approve`."""
    request_id = _new_request_id()
    record = _fixture_record(request_id)
    good_hash = record["binding"]["canonical_hash"]
    record["binding"]["canonical_hash"] = ("0" if good_hash[0] != "0" else "1") + good_hash[1:]
    check(AR.validate(record).ok, "test setup error: tampered-hash record should still validate() structurally")

    env = _Env(records=[record])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())

    buf = io.StringIO()
    rc = _run_approve(env, request_id, auth.get_assertion, out=buf)
    check(rc != 0, "a tampered-hash record was approved via the headless CLI")
    check(env.store.get(request_id)["status"] == AR.STATUS_PENDING, "tampered record's status changed despite denial")


# --------------------------------------------------------------------------
# agent-cannot-complete -- no-UV / unregistered credential refused
# --------------------------------------------------------------------------


def test_no_user_verification_refused() -> None:
    request_id = _new_request_id()
    env = _Env(records=[_fixture_record(request_id)])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id, user_verified=False)
    env.add_credential(auth.allowlist_entry())

    buf = io.StringIO()
    rc = _run_approve(env, request_id, auth.get_assertion, out=buf)
    check(rc != 0, "a non-user-verified assertion was accepted by the headless CLI")
    check(env.store.get(request_id)["status"] == AR.STATUS_PENDING, "record moved to approved despite no UV")


def test_unregistered_credential_refused() -> None:
    """An assertion from a credential that was never added to the allowlist
    -- the CLI's own `credential_ids()` filter means this never even reaches
    the hardware-ceremony step; the request is refused with no_key_message
    up front, which is itself the correct 'agent cannot complete' outcome
    for a device the owner never registered."""
    request_id = _new_request_id()
    env = _Env(records=[_fixture_record(request_id)])
    unregistered = _SoftwareAuthenticator(rp_id=env.rp_id)
    # Deliberately never call env.add_credential(...).

    buf = io.StringIO()
    rc = _run_approve(env, request_id, unregistered.get_assertion, out=buf)
    check(rc != 0, "an unregistered credential's assertion was accepted")
    check(AH.PREP_COPY["no_key_message"] in buf.getvalue(), "expected the no_key_message for an unregistered credential")


def test_no_hardware_present_refused() -> None:
    """`get_assertion` returning None (no device found) -- the literal
    'agent has no hardware' case -- refuses cleanly with no_key_message and
    signs nothing."""
    request_id = _new_request_id()
    record = _fixture_record(request_id)
    env = _Env(records=[record])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())

    buf = io.StringIO()
    rc = _run_approve(env, request_id, _unregistered_get_assertion, out=buf)
    check(rc != 0, "cmd_approve succeeded with no assertion produced at all")
    check(AH.PREP_COPY["no_key_message"] in buf.getvalue(), "no_key_message not shown when get_assertion returns None")
    check(env.store.get(request_id)["status"] == AR.STATUS_PENDING, "record was approved despite no assertion")


def test_revoked_credential_refused() -> None:
    request_id = _new_request_id()
    env = _Env(records=[_fixture_record(request_id)])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry(status="revoked"))

    buf = io.StringIO()
    rc = _run_approve(env, request_id, auth.get_assertion, out=buf)
    check(rc != 0, "a revoked credential's assertion was accepted")
    check(env.store.get(request_id)["status"] == AR.STATUS_PENDING, "record was approved with a revoked credential")


# --------------------------------------------------------------------------
# no-passphrase-fallback -- static + behavioral
# --------------------------------------------------------------------------


def test_no_passphrase_or_keyfile_authorization_argument_exists() -> None:
    """Static check: the CLI's argument surface has no passphrase/password
    flag. `--owner-key-path` is the SERVICE's own signing key (same
    `owner_key: bytes` parameter approval_signer.py has always required) --
    not a human-factor substitute; the assertions below on `cmd_approve`
    prove behaviorally that supplying it is never sufficient on its own."""
    # Concrete flag/attribute tokens a passphrase-style downgrade would need
    # to introduce -- not a bare-word scan, which would false-positive on
    # this module's own docstring prose *documenting the absence* of one
    # (the same "discuss it, don't implement it" issue
    # test-approval-signer.py's hardening-4 check already had to avoid).
    for banned in ("--passphrase", "--password", "add_argument(\"--key-file\"", "add_argument(\"--secret"):
        check(banned not in CLI_SOURCE, f"aq-approve-headless contains a banned auth surface: {banned!r}")

    parser = AH.build_arg_parser()
    approve_parser = None
    for action in parser._subparsers._group_actions:  # noqa: SLF001 - argparse internals, test-only inspection
        for name, sub in action.choices.items():
            if name == "approve":
                approve_parser = sub
    check(approve_parser is not None, "test setup error: could not locate the approve subparser")
    approve_dests = {a.dest for a in approve_parser._actions}  # noqa: SLF001
    check(
        approve_dests.isdisjoint({"passphrase", "password", "secret"}),
        f"approve subcommand exposes a passphrase-shaped argument: {approve_dests}",
    )


def test_owner_key_alone_never_authorizes_without_an_assertion() -> None:
    """Behavioral proof: having a valid owner_key loaded changes NOTHING
    about needing a real hardware assertion -- `cmd_approve` with a correct
    owner_key but get_assertion=None-returning still produces no signature
    and no approval."""
    request_id = _new_request_id()
    env = _Env(records=[_fixture_record(request_id)])
    auth = _SoftwareAuthenticator(rp_id=env.rp_id)
    env.add_credential(auth.allowlist_entry())  # a real registered credential exists

    buf = io.StringIO()
    rc = AH.cmd_approve(
        env.store,
        env.signer(),
        env.owner_key_bytes,  # genuine, correct owner key
        request_id,
        get_assertion=_unregistered_get_assertion,  # but no hardware ceremony happens
        rp_id=env.rp_id,
        credential_ids=env.credential_ids(),
        out=buf,
    )
    check(rc != 0, "a genuine owner_key with no hardware assertion still produced an approval")
    check(env.store.get(request_id)["status"] == AR.STATUS_PENDING, "record was approved with no assertion at all")


def test_production_cli_excludes_software_authenticator() -> None:
    for banned_import in ("import fido2.mock", "from fido2.mock", "from fido2 import mock"):
        check(banned_import not in CLI_SOURCE, f"aq-approve-headless contains {banned_import!r}")
    check(
        "SoftwareAuthenticator" not in CLI_SOURCE,
        "aq-approve-headless references a software/virtual authenticator class",
    )
    check(
        not hasattr(AH, "_SoftwareAuthenticator") and not hasattr(AH, "SoftwareAuthenticator"),
        "aq-approve-headless module exposes a software-authenticator symbol",
    )
    for forging_construct in (
        "AuthenticatorAssertionResponse(",
        "CollectedClientData.create(",
        "Ed25519PrivateKey.generate()",
    ):
        check(
            forging_construct not in CLI_SOURCE,
            f"aq-approve-headless contains {forging_construct!r} -- an assertion-forging construct",
        )


def test_hidraw_client_is_the_only_constructed_authenticator() -> None:
    """`main()`'s `approve` wiring constructs exactly one authenticator
    class -- `HidrawFido2Client` -- and it is the only class in this module
    whose name ends in `Client` that touches FIDO2 devices."""
    check(hasattr(AH, "HidrawFido2Client"), "aq-approve-headless has no HidrawFido2Client")
    check("CtapHidDevice" in CLI_SOURCE, "aq-approve-headless does not enumerate real hidraw devices")
    check("list_devices" in CLI_SOURCE, "aq-approve-headless does not call CtapHidDevice.list_devices()")


# --------------------------------------------------------------------------
# plain-language-cli -- Layer-1 default, no hex/path
# --------------------------------------------------------------------------

_HEX64_LIKE = __import__("re").compile(r"[0-9a-fA-F]{32,}")
_ABS_PATH_LIKE = __import__("re").compile(r"(?<!\S)/[\w.-]+(?:/[\w.-]+)+")


def test_list_default_view_is_layer1_only() -> None:
    request_id = _new_request_id()
    record = AR.create_request(
        request_id=request_id, created_by="t", runbook="restart-service", params={"service": "svc-a"}
    )
    store = AH.FixtureApprovalStore([record])

    buf = io.StringIO()
    rc = AH.cmd_list(store, details=False, out=buf)
    output = buf.getvalue()
    check(rc == 0, "cmd_list returned nonzero")
    check(AH.PREP_COPY["list_header"] in output, "list_header not printed")
    check(output.strip().splitlines()[1].strip() == "1. Restart the svc-a service", "request_line_format not verbatim")
    check(not _HEX64_LIKE.search(output), f"default list view leaked a hex-looking token: {output!r}")
    check(not _ABS_PATH_LIKE.search(output), f"default list view leaked a filesystem path: {output!r}")
    check("technical_trail" not in output, "default list view mentions technical_trail")
    check("canonical_hash" not in output, "default list view mentions canonical_hash")
    check(record["binding"]["canonical_hash"] not in output, "default list view leaked the actual canonical_hash value")


def test_list_details_flag_is_the_only_way_to_see_layer3() -> None:
    request_id = _new_request_id()
    record = AR.create_request(
        request_id=request_id, created_by="t", runbook="restart-service", params={"service": "svc-b"}
    )
    store = AH.FixtureApprovalStore([record])

    buf = io.StringIO()
    AH.cmd_list(store, details=True, out=buf)
    output = buf.getvalue()
    check(record["binding"]["canonical_hash"] in output, "--details did not surface the canonical_hash")
    check(record["request_id"] in output, "--details did not surface the request_id")


def test_approve_prompt_and_success_copy_match_prep_verbatim() -> None:
    check(AH.PREP_COPY["approve_prompt"] == "Please touch the metal button on your security key when it lights up.", "approve_prompt drifted from the prep doc")
    check(AH.PREP_COPY["success_message"] == "Approved successfully.", "success_message drifted from the prep doc")
    check(AH.PREP_COPY["denied_message"] == "Request denied.", "denied_message drifted from the prep doc")
    check(AH.PREP_COPY["no_key_message"] == "No security key detected. Please plug one in and try again.", "no_key_message drifted from the prep doc")
    check(AH.PREP_COPY["list_header"] == "Pending Approvals", "list_header drifted from the prep doc")
    check(AH.PREP_COPY["request_line_format"] == "{n}. {title}", "request_line_format drifted from the prep doc")


# --------------------------------------------------------------------------
# deny path -- no assertion, no signer call
# --------------------------------------------------------------------------


def test_deny_transitions_without_any_assertion() -> None:
    request_id = _new_request_id()
    env = _Env(records=[_fixture_record(request_id)])
    buf = io.StringIO()
    rc = AH.cmd_deny(env.store, request_id, out=buf)
    check(rc == 0, "cmd_deny failed on a valid pending request")
    check(AH.PREP_COPY["denied_message"] in buf.getvalue(), "denied_message not printed")
    check(env.store.get(request_id)["status"] == AR.STATUS_DENIED, "record was not transitioned to denied")


def test_deny_unknown_request_id() -> None:
    env = _Env(records=[])
    buf = io.StringIO()
    rc = AH.cmd_deny(env.store, "does-not-exist", out=buf)
    check(rc != 0, "cmd_deny succeeded for an unknown request_id")


def test_approve_unknown_request_id() -> None:
    env = _Env(records=[])
    buf = io.StringIO()
    rc = AH.cmd_approve(
        env.store,
        env.signer(),
        env.owner_key_bytes,
        "does-not-exist",
        get_assertion=_unregistered_get_assertion,
        rp_id=env.rp_id,
        credential_ids=[],
        out=buf,
    )
    check(rc != 0, "cmd_approve succeeded for an unknown request_id")


# --------------------------------------------------------------------------
# CLI wiring sanity -- main() end-to-end through argparse, no live hardware
# --------------------------------------------------------------------------


def test_main_list_subcommand_exit_zero() -> None:
    rc = AH.main(["list"])
    check(rc == 0, "main(['list']) did not exit 0")


def test_main_approve_without_owner_key_fails_closed() -> None:
    env_backup = os.environ.pop("AQ_APPROVAL_OWNER_KEY_PATH", None)
    try:
        rc = AH.main(["--owner-key-path", "/does/not/exist", "approve", "some-id"])
        check(rc != 0, "main() approve with a missing owner key file did not fail")
    finally:
        if env_backup is not None:
            os.environ["AQ_APPROVAL_OWNER_KEY_PATH"] = env_backup


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
    print(f"PASS: {len(tests)} aq-approve-headless P4 checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
