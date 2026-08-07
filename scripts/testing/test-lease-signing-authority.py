#!/usr/bin/env python3
"""Offline tests for the asymmetric first-party lease signing authority (ALA rev4 slice 2).

No network, no service, no /run/secrets. Generates its own throwaway Ed25519 keypair.
Proves: (1) minted leases verify under verify_authoritative; (2) FIELD PARITY with the gate's
own issue_first_party_leases() (anti-drift); (3) the authority mints from the manifest only —
no caller-payload parameter exists; (4) fail-closed signer-unavailable.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts", "ai", "lib"))
sys.path.insert(0, os.path.join(ROOT, "ai-stack", "switchboard"))

from datetime import datetime, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import capability_lease as cl
import lease_signing_authority as lsa
import capability_lease_gate as gate


def _keypair():
    priv = Ed25519PrivateKey.generate()
    priv_raw = priv.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    )
    pub_hex = priv.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    ).hex()
    return priv_raw, pub_hex


def main() -> int:
    failures = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    priv_raw, pub_hex = _keypair()
    key_id = "test-lease-signer"
    keys_json = {
        "schema_version": "1",
        "revision": 1,
        "keys": [{"key_id": key_id, "ed25519_public_key": pub_hex, "status": "active"}],
    }
    manifest = {
        "read_file": {"actions": ["read_file"], "resources": ["repo"], "trust_tier": 1,
                      "write_capable": False, "network_capable": False, "exec_capable": False},
        "run_cmd": {"actions": ["run_cmd"], "trust_tier": 3, "exec_capable": True,
                    "zero_trust_behavior": "sandbox"},
    }
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    epoch = 7

    # (1) mint + verify_authoritative accepts
    minted = lsa.mint_first_party_leases(manifest, epoch, priv_raw, key_id, now=now)
    check(set(minted) == set(manifest), "minted set should cover every manifest tool")
    for tool, lease in minted.items():
        check(lease.get("sig_scheme") == "ed25519", f"{tool}: sig_scheme must be ed25519")
        check(lease.get("issuer_key_id") == key_id, f"{tool}: issuer_key_id must be set")
        v = cl.verify_authoritative(lease, keys_json)
        check(v.ok, f"{tool}: verify_authoritative should accept a freshly-minted lease (got {v.reason})")

    # tampered field / forged sig deny
    bad = dict(minted["read_file"]); bad["trust_tier"] = 99
    check(not cl.verify_authoritative(bad, keys_json).ok, "tampered field must deny")

    # (2) FIELD PARITY with the gate's own issue_first_party_leases (anti-drift)
    gate.reset_first_party_lease_cache()
    gate_leases = gate.issue_first_party_leases(b"test-hmac-key-32-bytes-padding!!", epoch, manifest, now=now)
    gate.reset_first_party_lease_cache()
    IGNORE = {"signature", "sig_scheme", "issuer_key_id"}
    for tool in manifest:
        g = {k: v for k, v in gate_leases[tool].items() if k not in IGNORE}
        a = {k: v for k, v in minted[tool].items() if k not in IGNORE}
        if g != a:
            diff = {k: (g.get(k), a.get(k)) for k in set(g) | set(a) if g.get(k) != a.get(k)}
            check(False, f"{tool}: authority fields must match the gate's issue_first_party_leases; drift={diff}")

    # (3) the authority mints from the manifest only — no caller payload parameter
    import inspect
    params = set(inspect.signature(lsa.mint_first_party_leases).parameters)
    check("manifest" in params and "epoch" in params, "mint takes manifest+epoch")
    check(not (params & {"payload", "lease", "lease_dict"}), "mint must NOT accept a caller lease/payload")

    # (4) fail-closed signer-unavailable
    os.environ.pop(lsa.SIGNER_KEY_PATH_ENV, None)
    check(lsa._read_private_key() is None, "no key path -> None (fail-closed)")
    check(lsa.serve_once_stub() == lsa.DENY_SIGNER_UNAVAILABLE, "stub must report signer-unavailable without a key")

    # empty manifest -> empty
    check(lsa.mint_first_party_leases({}, epoch, priv_raw, key_id) == {}, "empty manifest -> {}")

    # (5) server handle_request round-trip with a real key on disk -> leases that verify
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".key", delete=False) as kf:
        kf.write(priv_raw.hex())
        keypath = kf.name
    try:
        os.environ[lsa.SIGNER_KEY_PATH_ENV] = keypath
        os.environ[lsa.SIGNER_KEY_ID_ENV] = key_id
        resp = lsa.handle_request(b'{"op":"mint-first-party"}\n')  # body IGNORED (authority self-derives)
        check("leases" in resp and isinstance(resp["leases"], dict), "handle_request returns a leases dict")
        for tool, lease in resp["leases"].items():
            check(cl.verify_authoritative(lease, keys_json).ok, f"server-minted {tool} must verify_authoritative")
    finally:
        os.environ.pop(lsa.SIGNER_KEY_PATH_ENV, None)
        os.environ.pop(lsa.SIGNER_KEY_ID_ENV, None)
        os.unlink(keypath)
    check(lsa.handle_request(b"{}").get("error") == lsa.DENY_SIGNER_UNAVAILABLE,
          "handle_request must fail-closed (signer-unavailable) with no key")

    # (6) gate client fail-closed: no socket path -> {} deny-all, never HMAC
    os.environ.pop("AQ_LEASE_SIGNING_SOCKET_PATH", None)
    check(gate._request_asymmetric_first_party_leases() == {},
          "gate asymmetric client must fail-closed to deny-all when the authority is unreachable")

    if failures:
        print("FAIL: lease signing authority")
        for f in failures:
            print("  - " + f)
        return 1
    print("PASS: lease signing authority valid (mint+verify, field-parity, mint-from-manifest, fail-closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
