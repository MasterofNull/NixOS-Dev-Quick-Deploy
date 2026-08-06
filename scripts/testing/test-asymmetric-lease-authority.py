#!/usr/bin/env python3
"""Offline acceptance tests for the Foundation C rev4 asymmetric (Ed25519)
capability-lease crypto primitive.

Covers the proof obligations from
`.agents/plans/aqos-foundation-c/ASYMMETRIC-LEASE-AUTHORITY-DESIGN-20260806.md`
(revision 4) and its freeze record
`.agents/plans/aqos-foundation-c/ASYMMETRIC-LEASE-AUTHORITY-FREEZE-20260806.md`:
`sign_ed25519`/`verify_authoritative` round-trip, forged/tampered-signature
denial, the scheme-downgrade guard (rev2 mandate 1 — no HMAC fallback, no
dev-key path reachable from `verify_authoritative`), unknown/revoked
key-id denial, malformed-`keys_json` deny-ALL, and byte-parity of
`canonical_payload()` plus the legacy HMAC `sign()`/`verify()` round-trip
for leases that carry NO `sig_scheme` (rev2 mandate 3).

Fully offline and self-contained: generates its own Ed25519 keypair and
builds its own `keys_json` allowlist in-test. No network, no service, no
dependency on `config/aqos/lease-signer-keys.json` or any `/run/secrets`
path.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIB_DIR = REPO_ROOT / "scripts" / "ai" / "lib"
sys.path.insert(0, str(LIB_DIR))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402
from cryptography.hazmat.primitives.serialization import (  # noqa: E402
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

import capability_lease as cl  # noqa: E402

passed = 0
failed = 0


def check(label: str, condition: bool) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"PASS: {label}")
    else:
        failed += 1
        print(f"FAIL: {label}")


# --------------------------------------------------------------------------
# In-test keypair + keys_json fixture (offline, self-contained)
# --------------------------------------------------------------------------

_PRIVATE_KEY = Ed25519PrivateKey.generate()
_PRIVATE_KEY_BYTES = _PRIVATE_KEY.private_bytes(
    encoding=Encoding.Raw,
    format=PrivateFormat.Raw,
    encryption_algorithm=NoEncryption(),
)
_PUBLIC_KEY_HEX = _PRIVATE_KEY.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()

ACTIVE_KEY_ID = "test-signer-active"
REVOKED_KEY_ID = "test-signer-revoked"

KEYS_JSON = {
    "schema_version": "1",
    "revision": 1,
    "keys": [
        {"key_id": ACTIVE_KEY_ID, "ed25519_public_key": _PUBLIC_KEY_HEX, "status": "active"},
        {"key_id": REVOKED_KEY_ID, "ed25519_public_key": _PUBLIC_KEY_HEX, "status": "revoked"},
    ],
}


def make_lease(**overrides) -> dict:
    base = {
        "lease_id": "lease-c-asymmetric-test-001",
        "sig_scheme": "ed25519",
        "issuer_key_id": ACTIVE_KEY_ID,
        "issued_to": "switchboard-local-tool-executor",
        "issued_at": "2026-08-06T00:00:00Z",
        "expires_at": "2026-08-07T00:00:00Z",
        "permissions": {"actions": ["read"], "resources": ["repo:test"], "constraints": {}},
        "input_schema": {},
        "output_schema": {},
        "trust_tier": 1,
        "zero_trust_behavior": "none",
        "revocation_epoch": 1,
    }
    base.update(overrides)
    return base


def sign_lease(lease: dict) -> dict:
    signed = dict(lease)
    signed["signature"] = cl.sign_ed25519(lease, _PRIVATE_KEY_BYTES)
    return signed


# --------------------------------------------------------------------------
# 1. sign_ed25519 + verify_authoritative round-trip PASSES
# --------------------------------------------------------------------------

valid_lease = sign_lease(make_lease())
verdict = cl.verify_authoritative(valid_lease, KEYS_JSON)
check("round-trip: valid ed25519 lease verifies OK", verdict.ok and verdict.reason == cl.AUTH_VERIFY_OK)

# --------------------------------------------------------------------------
# 2. FORGED / tampered signature -> deny
# --------------------------------------------------------------------------

forged = dict(valid_lease)
forged["signature"] = "00" * 64  # syntactically valid hex, cryptographically bogus
verdict = cl.verify_authoritative(forged, KEYS_JSON)
check("forged signature denies", not verdict.ok and verdict.reason == cl.AUTH_DENY_BAD_SIGNATURE)

garbage_sig = dict(valid_lease)
garbage_sig["signature"] = "not-hex-at-all"
verdict = cl.verify_authoritative(garbage_sig, KEYS_JSON)
check("non-hex signature denies", not verdict.ok and verdict.reason == cl.AUTH_DENY_BAD_SIGNATURE)

# --------------------------------------------------------------------------
# 3. Flipped field -> signature no longer matches -> deny
# --------------------------------------------------------------------------

flipped = dict(valid_lease)
flipped["trust_tier"] = 99
verdict = cl.verify_authoritative(flipped, KEYS_JSON)
check("flipped field (trust_tier) denies", not verdict.ok and verdict.reason == cl.AUTH_DENY_BAD_SIGNATURE)

flipped_perms = copy.deepcopy(valid_lease)
flipped_perms["permissions"]["actions"] = ["read", "write", "delegate"]
verdict = cl.verify_authoritative(flipped_perms, KEYS_JSON)
check("flipped nested field (permissions.actions) denies", not verdict.ok and verdict.reason == cl.AUTH_DENY_BAD_SIGNATURE)

# --------------------------------------------------------------------------
# 4. Scheme-downgrade: sig_scheme="hmac-sha256" or absent -> deny, NEVER
#    HMAC-verified, no dev-key fallback reachable.
# --------------------------------------------------------------------------

hmac_key, _is_dev = cl.resolve_key()

downgraded = make_lease(sig_scheme="hmac-sha256")
downgraded["signature"] = cl.sign(downgraded, hmac_key)  # genuinely valid HMAC sig
verdict = cl.verify_authoritative(downgraded, KEYS_JSON)
check(
    "scheme-downgrade (hmac-sha256, genuinely HMAC-signed) denies via verify_authoritative",
    not verdict.ok and verdict.reason == cl.AUTH_DENY_SCHEME,
)

absent_scheme = make_lease()
del absent_scheme["sig_scheme"]
absent_scheme["signature"] = cl.sign(absent_scheme, hmac_key)
verdict = cl.verify_authoritative(absent_scheme, KEYS_JSON)
check(
    "absent sig_scheme denies via verify_authoritative (no legacy-hmac default)",
    not verdict.ok and verdict.reason == cl.AUTH_DENY_SCHEME,
)

unknown_scheme = make_lease(sig_scheme="rot13")
unknown_scheme["signature"] = "aa" * 64
verdict = cl.verify_authoritative(unknown_scheme, KEYS_JSON)
check("unknown sig_scheme denies via verify_authoritative", not verdict.ok and verdict.reason == cl.AUTH_DENY_SCHEME)

# --------------------------------------------------------------------------
# 5. key_id unknown or revoked -> deny; malformed keys_json -> deny-all
# --------------------------------------------------------------------------

unknown_key = sign_lease(make_lease(issuer_key_id="no-such-key-id"))
verdict = cl.verify_authoritative(unknown_key, KEYS_JSON)
check("unknown key_id denies", not verdict.ok and verdict.reason == cl.AUTH_DENY_UNKNOWN_KEY)

revoked_lease = sign_lease(make_lease(issuer_key_id=REVOKED_KEY_ID))
verdict = cl.verify_authoritative(revoked_lease, KEYS_JSON)
check("revoked key_id (status != active) denies", not verdict.ok and verdict.reason == cl.AUTH_DENY_KEY_NOT_ACTIVE)

for label, bad_keys_json in (
    ("None", None),
    ("empty dict", {}),
    ("missing keys list", {"revision": 1}),
    ("keys not a list", {"revision": 1, "keys": "not-a-list"}),
    ("empty keys list", {"revision": 1, "keys": []}),
):
    verdict = cl.verify_authoritative(valid_lease, bad_keys_json)
    check(f"malformed keys_json ({label}) denies-ALL", not verdict.ok and verdict.reason == cl.AUTH_DENY_MALFORMED_KEYS)

# A structurally-present-but-entirely-garbage `keys` list contains no entry
# that can ever match a real key_id, so it also denies-ALL in effect (every
# non-dict entry is skipped by the lookup) — the reason surfaces as
# unknown-key-id rather than keys-malformed, but the outcome is the same
# fail-closed deny; no lease can ever pass against it.
verdict = cl.verify_authoritative(valid_lease, {"revision": 1, "keys": ["not-a-dict", 42]})
check(
    "keys_json with only garbage entries denies-ALL (no entry can ever match)",
    not verdict.ok and verdict.reason in (cl.AUTH_DENY_MALFORMED_KEYS, cl.AUTH_DENY_UNKNOWN_KEY),
)

# A well-formed keys_json whose matching entry has a malformed public key
# must also deny (not raise, not accept).
bad_pubkey_keys_json = {
    "revision": 1,
    "keys": [{"key_id": ACTIVE_KEY_ID, "ed25519_public_key": "not-hex", "status": "active"}],
}
verdict = cl.verify_authoritative(valid_lease, bad_pubkey_keys_json)
check("malformed public-key hex in matching key entry denies", not verdict.ok and verdict.reason == cl.AUTH_DENY_MALFORMED_KEYS)

# A non-mapping lease must deny rather than raise.
verdict = cl.verify_authoritative("not-a-lease", KEYS_JSON)
check("non-mapping lease denies (never raises)", not verdict.ok)

# --------------------------------------------------------------------------
# 6. Byte-parity: canonical_payload() of a legacy lease (no sig_scheme) is
#    byte-identical before/after the asymmetric edits, and the legacy HMAC
#    sign()/verify() round-trip is unchanged.
# --------------------------------------------------------------------------

EXPECTED_LEGACY_CANONICAL = (
    b'{"cost_class":"local","expires_at":"2026-12-31T00:00:00Z","input_schema":{},'
    b'"issued_at":"2026-08-06T00:00:00Z","issued_to":"test-principal",'
    b'"lease_id":"lease-test-legacy-001","output_schema":{},"owner":"test-owner",'
    b'"parent_lease_id":null,"permissions":{"actions":["read"],"constraints":{},'
    b'"resources":["repo:test"]},"revocation_epoch":1,"source":"test","trust_tier":1,'
    b'"version":1,"zero_trust_behavior":"none"}'
)
EXPECTED_LEGACY_HMAC_SIGNATURE = "bbcfd7f618696d1562d578f6a0bfcd1bf39f3d77ec4eb775c0efc601507042ac"

legacy_lease = {
    "lease_id": "lease-test-legacy-001",
    "version": 1,
    "source": "test",
    "owner": "test-owner",
    "issued_to": "test-principal",
    "issued_at": "2026-08-06T00:00:00Z",
    "expires_at": "2026-12-31T00:00:00Z",
    "permissions": {"actions": ["read"], "resources": ["repo:test"], "constraints": {}},
    "input_schema": {},
    "output_schema": {},
    "trust_tier": 1,
    "zero_trust_behavior": "none",
    "cost_class": "local",
    "parent_lease_id": None,
    "revocation_epoch": 1,
    "signature": "PLACEHOLDER",
}

actual_canonical = cl.canonical_payload(legacy_lease)
check(
    "byte-parity: legacy canonical_payload() unchanged (no sig_scheme field present)",
    actual_canonical == EXPECTED_LEGACY_CANONICAL,
)
check(
    "byte-parity: legacy sig_scheme absent from canonical bytes",
    b"sig_scheme" not in actual_canonical,
)

legacy_signature = cl.sign(legacy_lease, cl.DEV_SIGNING_KEY)
check("byte-parity: legacy HMAC sign() reproduces the pinned golden signature", legacy_signature == EXPECTED_LEGACY_HMAC_SIGNATURE)

legacy_signed = dict(legacy_lease)
legacy_signed["signature"] = legacy_signature
legacy_verify_result = cl.verify(legacy_signed, cl.DEV_SIGNING_KEY)
check("byte-parity: legacy HMAC verify() round-trips OK", legacy_verify_result == cl.VERIFY_OK)

tampered_legacy = dict(legacy_signed)
tampered_legacy["owner"] = "someone-else"
check(
    "byte-parity: tampered legacy lease fails legacy HMAC verify()",
    cl.verify(tampered_legacy, cl.DEV_SIGNING_KEY) == cl.VERIFY_BAD_SIGNATURE,
)

# --------------------------------------------------------------------------
# 7. verify_authoritative must NEVER be fooled by a legacy-shaped lease that
#    merely happens to carry a genuinely-valid HMAC signature (belt-and-
#    braces re-assertion of the scheme-downgrade guard from case 4, using
#    the exact legacy byte-parity fixture above).
# --------------------------------------------------------------------------

legacy_via_authoritative = cl.verify_authoritative(legacy_signed, KEYS_JSON)
check(
    "legacy HMAC-signed lease never authoritatively verifies (no sig_scheme)",
    not legacy_via_authoritative.ok and legacy_via_authoritative.reason == cl.AUTH_DENY_SCHEME,
)


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

print(f"\n{passed} passed, {failed} failed")
if failed == 0:
    print("PASS: asymmetric lease authority crypto valid")
    sys.exit(0)
else:
    sys.exit(1)
