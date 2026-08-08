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
if os.environ.get("AQ_CANDIDATE_LIB_DIR"):
    sys.path.insert(0, os.environ["AQ_CANDIDATE_LIB_DIR"])

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
    minted = lsa.mint_first_party_leases(manifest, epoch, priv_raw, key_id, policy_revision=9, now=now)
    check(set(minted) == set(manifest), "minted set should cover every manifest tool")
    for tool, lease in minted.items():
        check(lease.get("sig_scheme") == "ed25519", f"{tool}: sig_scheme must be ed25519")
        check(lease.get("issuer_key_id") == key_id, f"{tool}: issuer_key_id must be set")
        check(lease.get("policy_revision") == 9, f"{tool}: policy revision must be signed")
        check(len(lease.get("grant_digest", "")) == 64, f"{tool}: canonical grant digest is required")
        v = cl.verify_authoritative(lease, keys_json)
        check(v.ok, f"{tool}: verify_authoritative should accept a freshly-minted lease (got {v.reason})")

    # tampered field / forged sig deny
    bad = dict(minted["read_file"]); bad["trust_tier"] = 99
    check(not cl.verify_authoritative(bad, keys_json).ok, "tampered field must deny")

    # (2) FIELD PARITY with the gate's own issue_first_party_leases (anti-drift)
    gate.reset_first_party_lease_cache()
    gate_leases = gate.issue_first_party_leases(b"test-hmac-key-32-bytes-padding!!", epoch, manifest, now=now)
    gate.reset_first_party_lease_cache()
    IGNORE = {"signature", "sig_scheme", "issuer_key_id", "policy_revision", "grant_digest"}
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
    check(lsa.mint_first_party_leases({}, epoch, priv_raw, key_id, 9) == {}, "empty manifest -> {}")
    check(lsa.mint_first_party_leases(manifest, epoch, priv_raw, key_id, 0) == {}, "bad revision -> deny-all")

    one = minted["read_file"]
    rotated = lsa.mint_first_party_leases(manifest, epoch + 1, priv_raw, key_id, policy_revision=9,
                                          now=now.replace(second=6))["read_file"]
    changed = dict(manifest); changed["read_file"] = {**manifest["read_file"], "trust_tier": 2}
    changed_lease = lsa.mint_first_party_leases(changed, epoch, priv_raw, key_id, policy_revision=9, now=now)["read_file"]
    check(one["grant_digest"] == rotated["grant_digest"], "time and epoch do not alter policy identity")
    check(one["grant_digest"] != changed_lease["grant_digest"], "authority mutation changes policy identity")

    # (5) server handle_request round-trip with a real key on disk -> leases that verify
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".key", delete=False) as kf:
        kf.write(priv_raw.hex())
        keypath = kf.name
    try:
        os.environ[lsa.SIGNER_KEY_PATH_ENV] = keypath
        os.environ[lsa.SIGNER_KEY_ID_ENV] = key_id
        original_manifest_path = lsa.DEFAULT_MANIFEST_PATH
        lsa.DEFAULT_MANIFEST_PATH = os.path.join(os.environ.get("AQ_SOURCE_ROOT", ROOT), "config", "first-party-tools.json")
        original_resolve_epoch = lsa._resolve_epoch
        lsa._resolve_epoch = lambda: epoch
        # Service loader is separately tested with a real manifest in its temp path; request is ignored.
        resp = lsa.handle_request(b'{"op":"mint-first-party"}\n')
        check("leases" in resp and isinstance(resp["leases"], dict), "handle_request returns a leases dict")
        for tool, lease in resp["leases"].items():
            check(cl.verify_authoritative(lease, keys_json).ok, f"server-minted {tool} must verify_authoritative")
        # The live authority boundary must never fall back to file/env/0 when its strict epoch
        # resolver cannot prove current state.  Four representative source failures share the
        # one typed external outcome and return no leases.
        import revocation_epoch as re_lib
        for reason in ("missing-socket", "authority-deny", "malformed-response", "malformed-durable-state"):
            def _raise_epoch(_reason=reason):
                raise re_lib.EpochAuthorityError(_reason)
            lsa._resolve_epoch = _raise_epoch
            denied = lsa.handle_request(b"{}")
            check(denied == {"error": lsa.DENY_EPOCH_AUTHORITY_UNAVAILABLE},
                  f"ALA {reason} -> typed epoch-authority-unavailable, never zero")
        lsa._resolve_epoch = lambda: epoch
    finally:
        lsa._resolve_epoch = original_resolve_epoch
        lsa.DEFAULT_MANIFEST_PATH = original_manifest_path
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
