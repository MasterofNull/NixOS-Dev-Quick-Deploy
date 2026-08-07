#!/usr/bin/env python3
"""Offline acceptance tests — ALA-ENFORCE (enforce-asymmetric-verify).

Covers the 11 hermetic admission vectors from
`.agents/plans/aqos-foundation-c/ENFORCE-ASYMMETRIC-VERIFY-DESIGN-20260807.md`
(rev2, frozen `.agents/plans/aqos-foundation-c/ENFORCE-ASYMMETRIC-VERIFY-FREEZE-20260807.md`,
design SHA-256 `6a2e5f84423ac67d3987fdc3b6c0ddbfb58010734859a222a4a556be80fb9cd5`):
scheme-dispatched admission verify (`capability_lease_gate._admission_verify`)
for `enforce()`'s candidate and first-party branches — ed25519 admit/deny
cases (expired, epoch-stale, bad-signature, unknown/revoked key), legacy
HMAC byte-parity (N1's `keys_json` load never touches the HMAC path), the
N1 fail-closed keys-load sentinel (malformed content + a genuine read
raise), the N2 in-try/except placement (a signed-but-malformed
`expires_at` denies ONE tool without escaping to the S-c wrapper), and N4
epoch-source parity (stamped-at-enforce-epoch admits; stamped-stale
denies).

Mints real Ed25519 test leases with `capability_lease.sign_ed25519` against
a throwaway in-test keypair + a matching test `keys_json` allowlist —
fully offline and self-contained, no dependency on
`config/aqos/lease-signer-keys.json` or any `/run/secrets` path (the
module's `DEFAULT_LEASE_SIGNER_KEYS_PATH` is monkeypatched per-test to a
temp fixture and always restored).

Run directly: `python3 scripts/testing/test-enforce-asymmetric-verify.py`
Exits 0 iff every test passes; each failure prints tool/expected/actual.
"""

from __future__ import annotations

import contextlib
import copy
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SWITCHBOARD_DIR = str(_REPO_ROOT / "ai-stack" / "switchboard")
_LIB_DIR = str(_REPO_ROOT / "scripts" / "ai" / "lib")
for _p in (_SWITCHBOARD_DIR, _LIB_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import (  # noqa: E402
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

import capability_lease as cl  # noqa: E402
import capability_lease_gate as gate  # noqa: E402

MANIFEST_PATH = _REPO_ROOT / "config" / "first-party-tools.json"

# --------------------------------------------------------------------------
# Test harness (no external deps)
# --------------------------------------------------------------------------

_RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _RESULTS.append((name, bool(condition), str(detail)))


def _report_and_exit() -> None:
    failed = [r for r in _RESULTS if not r[1]]
    for name, ok, detail in _RESULTS:
        status = "PASS" if ok else "FAIL"
        line = f"[{status}] {name}"
        if detail and not ok:
            line += f" — {detail}"
        print(line)
    print(f"\n{len(_RESULTS) - len(failed)}/{len(_RESULTS)} passed")
    if failed:
        print(f"FAILED: {[f[0] for f in failed]}")
        sys.exit(1)
    sys.exit(0)


# --------------------------------------------------------------------------
# In-test Ed25519 keypair + keys_json fixture (offline, self-contained)
# --------------------------------------------------------------------------

_PRIVATE_KEY = Ed25519PrivateKey.generate()
_PRIVATE_KEY_BYTES = _PRIVATE_KEY.private_bytes(
    encoding=Encoding.Raw,
    format=PrivateFormat.Raw,
    encryption_algorithm=NoEncryption(),
)
_PUBLIC_KEY_HEX = _PRIVATE_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

ACTIVE_KEY_ID = "test-ala-enforce-active"
REVOKED_KEY_ID = "test-ala-enforce-revoked"
UNKNOWN_KEY_ID = "test-ala-enforce-not-in-allowlist"

KEYS_JSON = {
    "schema_version": "1",
    "revision": 1,
    "keys": [
        {"key_id": ACTIVE_KEY_ID, "ed25519_public_key": _PUBLIC_KEY_HEX, "status": "active"},
        {"key_id": REVOKED_KEY_ID, "ed25519_public_key": _PUBLIC_KEY_HEX, "status": "revoked"},
    ],
}

PROD_KEY = b"test-enforce-asymmetric-verify-hmac-prod-key-0123456789"


def prod_resolver():
    return PROD_KEY, False


# --------------------------------------------------------------------------
# Manifest fixture (real on-disk manifest, read-only — never mutated)
# --------------------------------------------------------------------------

_MANIFEST_RAW = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
MANIFEST_TOOLS = {entry["tool"]: entry for entry in _MANIFEST_RAW["tools"]}
BUNDLE_TOOLS = set(MANIFEST_TOOLS.keys())  # trivially set-equal to the manifest itself


def reset_gate_state() -> None:
    gate.reset_first_party_lease_cache()
    gate.reset_manifest_cache()


def base_ctx(**overrides) -> dict:
    ctx = {
        "zero_trust_behavior": "none",
        "candidate_leases": [],
        "bundle_tools": BUNDLE_TOOLS,
    }
    ctx.update(overrides)
    return ctx


@contextlib.contextmanager
def patched_keys_path(content, *, as_directory: bool = False):
    """Monkeypatch `gate.DEFAULT_LEASE_SIGNER_KEYS_PATH` for the duration of
    the `with` block, then restore it. `content`: a dict (written as JSON),
    a raw str (written verbatim — for malformed-JSON fixtures), or None
    (only valid with `as_directory=True`, to induce a genuine read raise —
    `Path(dir).read_text()` raises `IsADirectoryError`, exercising the REAL
    `_load_lease_signer_keys_json` fail-closed path, not a mock)."""
    original = gate.DEFAULT_LEASE_SIGNER_KEYS_PATH
    with tempfile.TemporaryDirectory() as td:
        try:
            if as_directory:
                gate.DEFAULT_LEASE_SIGNER_KEYS_PATH = Path(td)
            else:
                target = Path(td) / "lease-signer-keys.json"
                if isinstance(content, str):
                    target.write_text(content, encoding="utf-8")
                else:
                    target.write_text(json.dumps(content), encoding="utf-8")
                gate.DEFAULT_LEASE_SIGNER_KEYS_PATH = target
            yield
        finally:
            gate.DEFAULT_LEASE_SIGNER_KEYS_PATH = original


# --------------------------------------------------------------------------
# Lease fixtures
# --------------------------------------------------------------------------


def make_ed25519_first_party_lease(
    tool: str,
    manifest_entry: dict,
    private_key_bytes: bytes,
    key_id: str,
    *,
    expires_at: str = None,
    revocation_epoch: int = 0,
) -> dict:
    """Build a first-party-shaped Ed25519 lease whose bound security
    metadata (actions/resources/constraints/risk/trust_tier/
    zero_trust_behavior) exactly matches `manifest_entry` — so the codex-3
    tamper/drift tripwire in `enforce()` never interferes with these tests,
    which are exclusively about the N1-N4 verify dispatch."""
    moment = datetime.now(timezone.utc)
    lease: dict = {
        "lease_id": f"first-party::{tool}::ed25519-test::{moment.isoformat()}",
        "version": 1,
        "source": "first-party-manifest",
        "owner": "first-party-manifest",
        "issued_to": "switchboard-local-tool-executor",
        "issued_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": expires_at
        if expires_at is not None
        else (moment + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "permissions": {
            "actions": list(manifest_entry.get("actions") or [tool]),
            "resources": list(manifest_entry.get("resources") or []),
            "constraints": {
                "risk": {
                    "write_capable": bool(manifest_entry.get("write_capable", False)),
                    "network_capable": bool(manifest_entry.get("network_capable", False)),
                    "exec_capable": bool(manifest_entry.get("exec_capable", False)),
                    "trust_tier": int(manifest_entry.get("trust_tier", 0)),
                },
            },
        },
        "input_schema": {},
        "output_schema": {},
        "trust_tier": int(manifest_entry.get("trust_tier", 0)),
        "zero_trust_behavior": str(manifest_entry.get("zero_trust_behavior", "none")),
        "cost_class": "first-party",
        "parent_lease_id": None,
        "revocation_epoch": int(revocation_epoch),
        "sig_scheme": cl.SIG_SCHEME_ED25519,
        "issuer_key_id": key_id,
        "signature": "",
    }
    lease["signature"] = cl.sign_ed25519(lease, private_key_bytes)
    return lease


def make_hmac_candidate_lease(
    tool: str,
    key: bytes,
    *,
    expires_delta: timedelta = timedelta(hours=1),
    revocation_epoch: int = 0,
) -> dict:
    """Legacy (no `sig_scheme`) HMAC candidate lease — the byte-identical
    pre-slice path. Used as a control alongside ed25519 fixtures to prove
    isolation (a failure/deny on the ed25519 side never bleeds into HMAC
    admission)."""
    moment = datetime.now(timezone.utc)
    lease: dict = {
        "lease_id": f"candidate::{tool}::{moment.isoformat()}",
        "version": 1,
        "source": "capability-intake-shadow",
        "owner": "capability-intake-shadow",
        "issued_to": "candidate:test",
        "issued_at": moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": (moment + expires_delta).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "permissions": {"actions": [tool], "resources": [], "constraints": {}},
        "input_schema": {},
        "output_schema": {},
        "trust_tier": 3,
        "zero_trust_behavior": "none",
        "cost_class": "shadow",
        "parent_lease_id": None,
        "revocation_epoch": revocation_epoch,
        "signature": "",
    }
    lease["signature"] = cl.sign(lease, key)
    return lease


RUN_COMMAND_ENTRY = MANIFEST_TOOLS["run_command"]


# --------------------------------------------------------------------------
# V1 — Ed25519 first-party lease (authority-minted shape, current epoch,
#      unexpired) -> ADMIT.
# --------------------------------------------------------------------------


def test_v1_ed25519_first_party_admits():
    reset_gate_state()
    with patched_keys_path(KEYS_JSON):
        lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID, revocation_epoch=0
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": lease}
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check("v1_ed25519_first_party_admits", "run_command" in admitted, admitted)
        d = next(dd for dd in decisions if dd["tool"] == "run_command")
        check("v1_ed25519_first_party_reason", d["reason"] == "first-party-lease-verified", d)
        check("v1_ed25519_first_party_source", d["source"] == "first-party", d)
    reset_gate_state()


# --------------------------------------------------------------------------
# V2 — expired ed25519 lease -> DENY first-party-lease-expired
# --------------------------------------------------------------------------


def test_v2_ed25519_expired_denies():
    reset_gate_state()
    with patched_keys_path(KEYS_JSON):
        past = (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID,
            expires_at=past, revocation_epoch=0,
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": lease}
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check("v2_ed25519_expired_denied", "run_command" not in admitted, admitted)
        d = next(dd for dd in decisions if dd["tool"] == "run_command")
        check("v2_ed25519_expired_reason", d["reason"] == f"first-party-lease-{cl.VERIFY_EXPIRED}", d)
    reset_gate_state()


# --------------------------------------------------------------------------
# V3 — revocation_epoch < current_epoch -> DENY first-party-lease-epoch-stale
# --------------------------------------------------------------------------


def test_v3_ed25519_epoch_stale_denies():
    reset_gate_state()
    with patched_keys_path(KEYS_JSON):
        lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID, revocation_epoch=0
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": lease}
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 5, prod_resolver)
        check("v3_ed25519_epoch_stale_denied", "run_command" not in admitted, admitted)
        d = next(dd for dd in decisions if dd["tool"] == "run_command")
        check("v3_ed25519_epoch_stale_reason", d["reason"] == f"first-party-lease-{cl.VERIFY_EPOCH_STALE}", d)
        # Control: the SAME lease admits at its own (matching) epoch — proves
        # the denial above is really epoch-staleness, not some other defect.
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": lease}
        admitted_ok, _ = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check("v3_control_admits_at_matching_epoch", "run_command" in admitted_ok, admitted_ok)
    reset_gate_state()


# --------------------------------------------------------------------------
# V4 — signature byte-flipped -> DENY first-party-lease-auth-bad-signature
# --------------------------------------------------------------------------


def test_v4_ed25519_bad_signature_denies():
    reset_gate_state()
    with patched_keys_path(KEYS_JSON):
        lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID, revocation_epoch=0
        )
        tampered = copy.deepcopy(lease)
        sig = tampered["signature"]
        flipped_char = "1" if sig[0] == "0" else "0"
        tampered["signature"] = flipped_char + sig[1:]
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": tampered}
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check("v4_ed25519_bad_signature_denied", "run_command" not in admitted, admitted)
        d = next(dd for dd in decisions if dd["tool"] == "run_command")
        check(
            "v4_ed25519_bad_signature_reason",
            d["reason"] == f"first-party-lease-auth-{cl.AUTH_DENY_BAD_SIGNATURE}",
            d,
        )
    reset_gate_state()


# --------------------------------------------------------------------------
# V5 — key_id not in allowlist / status:revoked -> DENY auth-unknown-key-id
#      / auth-key-not-active
# --------------------------------------------------------------------------


def test_v5a_ed25519_unknown_key_id_denies():
    reset_gate_state()
    with patched_keys_path(KEYS_JSON):
        lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, UNKNOWN_KEY_ID, revocation_epoch=0
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": lease}
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check("v5a_ed25519_unknown_key_id_denied", "run_command" not in admitted, admitted)
        d = next(dd for dd in decisions if dd["tool"] == "run_command")
        check(
            "v5a_ed25519_unknown_key_id_reason",
            d["reason"] == f"first-party-lease-auth-{cl.AUTH_DENY_UNKNOWN_KEY}",
            d,
        )
    reset_gate_state()


def test_v5b_ed25519_revoked_key_denies():
    reset_gate_state()
    with patched_keys_path(KEYS_JSON):
        lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, REVOKED_KEY_ID, revocation_epoch=0
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": lease}
        admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
        check("v5b_ed25519_revoked_key_denied", "run_command" not in admitted, admitted)
        d = next(dd for dd in decisions if dd["tool"] == "run_command")
        check(
            "v5b_ed25519_revoked_key_reason",
            d["reason"] == f"first-party-lease-auth-{cl.AUTH_DENY_KEY_NOT_ACTIVE}",
            d,
        )
    reset_gate_state()


# --------------------------------------------------------------------------
# V6 — legacy HMAC first-party lease (no sig_scheme) -> ADMIT via the
#      byte-identical HMAC path (parity)
# --------------------------------------------------------------------------


def test_v6_legacy_hmac_first_party_admits():
    reset_gate_state()
    admitted, decisions = gate.enforce({"run_command"}, base_ctx(), 0, prod_resolver)
    check("v6_legacy_hmac_first_party_admits", "run_command" in admitted, admitted)
    d = next(dd for dd in decisions if dd["tool"] == "run_command")
    check("v6_legacy_hmac_first_party_reason", d["reason"] == "first-party-lease-verified", d)
    lease = gate._FIRST_PARTY_LEASE_CACHE["run_command"]
    check("v6_legacy_hmac_lease_has_no_sig_scheme", "sig_scheme" not in lease, lease)
    reset_gate_state()


# --------------------------------------------------------------------------
# V7 — malformed keys_json content -> ALL ed25519 leases DENY; HMAC leases
#      UNAFFECTED (N1)
# --------------------------------------------------------------------------


def test_v7_malformed_keys_json_denies_ed25519_hmac_unaffected():
    reset_gate_state()
    with patched_keys_path("{ this is not valid json ["):
        lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID, revocation_epoch=0
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": lease}
        candidate = make_hmac_candidate_lease("custom_ext_tool", PROD_KEY)
        admitted, decisions = gate.enforce(
            {"run_command", "custom_ext_tool"},
            base_ctx(candidate_leases=[candidate]),
            0,
            prod_resolver,
        )
        check("v7_malformed_keys_json_denies_ed25519", "run_command" not in admitted, admitted)
        check("v7_malformed_keys_json_hmac_unaffected", "custom_ext_tool" in admitted, admitted)
        d = next(dd for dd in decisions if dd["tool"] == "run_command")
        check(
            "v7_malformed_keys_json_reason",
            d["reason"] == f"first-party-lease-auth-{cl.AUTH_DENY_MALFORMED_KEYS}",
            d,
        )
    reset_gate_state()


# --------------------------------------------------------------------------
# V8 — flag-off / sig_scheme-absent corpus -> enforce() decisions
#      byte-identical to pre-change (regression): `_admission_verify`'s
#      HMAC-fallback branch must return EXACTLY what `cl.verify()` returns,
#      for every representative case (valid/expired/epoch-stale/bad-sig/
#      malformed).
# --------------------------------------------------------------------------


def _legacy_corpus() -> list[tuple[str, dict, int]]:
    valid = make_hmac_candidate_lease("t_valid", PROD_KEY)
    expired = make_hmac_candidate_lease("t_expired", PROD_KEY, expires_delta=timedelta(hours=-1))
    stale = make_hmac_candidate_lease("t_stale", PROD_KEY, revocation_epoch=0)
    bad_sig = copy.deepcopy(valid)
    bad_sig["signature"] = "0" * 64
    malformed = copy.deepcopy(valid)
    del malformed["expires_at"]
    return [
        ("valid", valid, 0),
        ("expired", expired, 0),
        ("epoch_stale", stale, 5),
        ("bad_sig", bad_sig, 0),
        ("malformed", malformed, 0),
    ]


def test_v8_flag_off_sig_scheme_absent_byte_identical_regression():
    for label, lease, epoch in _legacy_corpus():
        direct = cl.verify(lease, PROD_KEY, current_epoch=epoch)
        dispatched = gate._admission_verify(lease, PROD_KEY, epoch, {})
        check(
            f"v8_byte_identical_{label}",
            dispatched == direct,
            f"dispatched={dispatched!r} direct={direct!r}",
        )
    # Sanity: "valid" really is VERIFY_OK (proves the corpus is meaningful,
    # not vacuously identical because every case is malformed).
    valid_lease = _legacy_corpus()[0][1]
    check(
        "v8_valid_case_is_actually_ok",
        cl.verify(valid_lease, PROD_KEY, current_epoch=0) == cl.VERIFY_OK,
        valid_lease,
    )


# --------------------------------------------------------------------------
# V9 — (N2) signed-but-malformed `expires_at` -> DENY for THAT tool only;
#      the exception must NOT escape the branch (other tools / HMAC leases
#      still evaluate — no total-deny via the S-c wrapper).
# --------------------------------------------------------------------------


def test_v9_malformed_expires_at_one_tool_deny_no_escape():
    reset_gate_state()
    with patched_keys_path(KEYS_JSON):
        bad_lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID,
            expires_at="not-a-valid-iso-timestamp", revocation_epoch=0,
        )
        # Fixture sanity: prove this lease genuinely triggers the raise this
        # vector is about (verify_authoritative does not pre-validate
        # expires_at — only is_expired()'s _parse_iso does).
        raised = False
        try:
            cl.is_expired(bad_lease)
        except Exception:
            raised = True
        check("v9_fixture_sanity_is_expired_raises", raised)

        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": bad_lease}
        control_candidate = make_hmac_candidate_lease("custom_ext_tool", PROD_KEY)
        admitted, decisions = gate.enforce(
            {"run_command", "custom_ext_tool"},
            base_ctx(candidate_leases=[control_candidate]),
            0,
            prod_resolver,
        )
        check("v9_malformed_expires_at_denies_only_that_tool", "run_command" not in admitted, admitted)
        check("v9_malformed_expires_at_no_escape_other_tool_admits", "custom_ext_tool" in admitted, admitted)
        d = next(dd for dd in decisions if dd["tool"] == "run_command")
        check("v9_malformed_expires_at_reason", d["reason"] == f"first-party-lease-{cl.VERIFY_MALFORMED}", d)
        for dec in decisions:
            check(
                f"v9_no_gate_exception_{dec['tool']}",
                not str(dec["reason"]).startswith("gate-exception:"),
                dec,
            )
    reset_gate_state()


# --------------------------------------------------------------------------
# V10 — (N1) keys-file read/parse raises (simulated via a real IsADirectory
#       read) -> the load returns the deny-all sentinel; ed25519 leases
#       DENY, HMAC leases ADMIT; no exception reaches the S-c wrapper.
# --------------------------------------------------------------------------


def test_v10_keys_file_raise_sentinel_no_escape():
    reset_gate_state()
    with patched_keys_path(None, as_directory=True):
        lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID, revocation_epoch=0
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": lease}
        control_candidate = make_hmac_candidate_lease("custom_ext_tool", PROD_KEY)
        admitted, decisions = gate.enforce(
            {"run_command", "custom_ext_tool"},
            base_ctx(candidate_leases=[control_candidate]),
            0,
            prod_resolver,
        )
        check("v10_keys_raise_denies_ed25519", "run_command" not in admitted, admitted)
        check("v10_keys_raise_hmac_admits", "custom_ext_tool" in admitted, admitted)
        for dec in decisions:
            check(
                f"v10_no_gate_exception_{dec['tool']}",
                not str(dec["reason"]).startswith("gate-exception:"),
                dec,
            )
        # Sanity: the REAL (unmocked) loader itself, called standalone,
        # returns the {} sentinel rather than raising.
        sentinel = gate._load_lease_signer_keys_json()
        check("v10_loader_sentinel_is_empty_dict", sentinel == {}, sentinel)
    reset_gate_state()


# --------------------------------------------------------------------------
# V11 — (N4) epoch-source parity: a lease stamped at the enforce-resolved
#       epoch ADMITS; a lease stamped at authority-epoch < enforce-epoch
#       DENIES epoch-stale (the mismatch-denies leg).
# --------------------------------------------------------------------------


def test_v11_epoch_source_parity():
    reset_gate_state()
    with patched_keys_path(KEYS_JSON):
        enforce_epoch = 3
        matching_lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID,
            revocation_epoch=enforce_epoch,
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": matching_lease}
        admitted_ok, _ = gate.enforce({"run_command"}, base_ctx(), enforce_epoch, prod_resolver)
        check("v11_epoch_parity_admits_when_stamped_at_enforce_epoch", "run_command" in admitted_ok, admitted_ok)

        gate.reset_first_party_lease_cache()
        stale_lease = make_ed25519_first_party_lease(
            "run_command", RUN_COMMAND_ENTRY, _PRIVATE_KEY_BYTES, ACTIVE_KEY_ID,
            revocation_epoch=enforce_epoch - 1,
        )
        gate._FIRST_PARTY_LEASE_CACHE = {"run_command": stale_lease}
        admitted_stale, decisions_stale = gate.enforce({"run_command"}, base_ctx(), enforce_epoch, prod_resolver)
        check("v11_epoch_parity_mismatch_denies_epoch_stale", "run_command" not in admitted_stale, admitted_stale)
        d = next(dd for dd in decisions_stale if dd["tool"] == "run_command")
        check(
            "v11_epoch_parity_mismatch_reason",
            d["reason"] == f"first-party-lease-{cl.VERIFY_EPOCH_STALE}",
            d,
        )
    reset_gate_state()


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

_TESTS = [
    test_v1_ed25519_first_party_admits,
    test_v2_ed25519_expired_denies,
    test_v3_ed25519_epoch_stale_denies,
    test_v4_ed25519_bad_signature_denies,
    test_v5a_ed25519_unknown_key_id_denies,
    test_v5b_ed25519_revoked_key_denies,
    test_v6_legacy_hmac_first_party_admits,
    test_v7_malformed_keys_json_denies_ed25519_hmac_unaffected,
    test_v8_flag_off_sig_scheme_absent_byte_identical_regression,
    test_v9_malformed_expires_at_one_tool_deny_no_escape,
    test_v10_keys_file_raise_sentinel_no_escape,
    test_v11_epoch_source_parity,
]


def main() -> None:
    for test_fn in _TESTS:
        try:
            test_fn()
        except Exception as exc:  # noqa: BLE001 — surface as a failed check, not a crash
            check(test_fn.__name__, False, f"raised {type(exc).__name__}: {exc}")
        finally:
            reset_gate_state()
    _report_and_exit()


if __name__ == "__main__":
    main()
