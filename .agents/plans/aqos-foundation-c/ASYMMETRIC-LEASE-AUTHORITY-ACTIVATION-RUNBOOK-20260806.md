# ALA rev4 — Activation Runbook (default-OFF → live)

The build is complete + default-OFF. Activation is a **two-phase, two-rebuild** sequence, gated on the
owner's SOPS key. It is sequenced key-first so the `CAPABILITY_ASYMMETRIC_LEASE=1` flip never causes a
fail-closed outage (an enabled flag without a provisioned key → authority denies → no first-party
leases → everything denied). Rollback is a single flag flip.

## Phase 0 — OWNER: provision the Ed25519 keypair (your sops key; Claude never sees the private)

Run in your shell (`!`):
```
python3 -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization
k=Ed25519PrivateKey.generate()
priv=k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()).hex()
pub=k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()
open('/tmp/ala-priv.hex','w').write(priv)
print('PUBLIC_KEY_HEX:', pub)
"
# add the private under key name  lease-signing-ed25519-private-key  (paste the /tmp/ala-priv.hex value):
sops nix/hosts/hyperd/secrets.sops.yaml
shred -u /tmp/ala-priv.hex
```
Then paste me the `PUBLIC_KEY_HEX`. (The private key stays entirely on your side, sops-encrypted; the
public key is non-secret.)

## Phase 1 — CLAUDE wires + OWNER rebuilds (flag stays 0 → NO outage)
Once you give me the public key, I:
1. put it in `config/aqos/lease-signer-keys.json` (replacing the placeholder `524279cd…`);
2. add the secret to `nix/modules/core/secrets.nix`: `"lease-signing-ed25519-private-key" = { mode = "0400"; owner = "aq-lease-signing-authority"; group = "aq-lease-signing-authority"; }` (mirrors `aq-grant-signing-key`);
3. set `mySystem.aiStack.leaseSigningAuthority.enable = true` in the ai-dev profile — creating the user + the confined service, with `CAPABILITY_ASYMMETRIC_LEASE` STILL 0 (the gate keeps using in-process HMAC).
4. run the WR-3-style bundle preflight and commit.

You rebuild. Verify (no outage — gate still HMAC):
```
! systemctl status aq-lease-signing-authority.service     # active
! sudo -u aq-lease-signing-authority AQ_LEASE_SIGNING_KEY_PATH=/run/secrets/lease-signing-ed25519-private-key python3 <bundle>/lease_signing_authority.py --check   # -> "ready"
```

## Phase 2 — flip the flag + validate the live mint
When Phase 1 is confirmed healthy, I flip `CAPABILITY_ASYMMETRIC_LEASE=1` (switchboard.nix) + commit;
you rebuild. Then I validate end-to-end:
- the gate's `issue_first_party_leases` now requests from the authority over UDS;
- a real first-party lease is Ed25519-signed (`sig_scheme=ed25519`) by the confined authority;
- `capability_lease.verify_authoritative` accepts it against `lease-signer-keys.json`;
- the switchboard (owner uid) never held the private key.

## Rollback (forward-safe)
`CAPABILITY_ASYMMETRIC_LEASE=0` + rebuild → the gate returns to in-process HMAC (byte-parity); the
service can stay enabled (inert) or be disabled. No lease state is lost.

## Notes
- Phase 1's flag-0 rebuild is the safe canary (service + key proven before any behavior change) — the R6 pattern.
- The public key in `lease-signer-keys.json` MUST match the sops-provisioned private key, else every
  `verify_authoritative` denies (fail-closed, not a leak).
- After activation, the C2 issuer rev3 can verify these live ed25519 leases; the issuer build should
  follow ALA activation, not precede it.
