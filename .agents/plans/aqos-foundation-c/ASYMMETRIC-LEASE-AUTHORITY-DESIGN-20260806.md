---
title: "Foundation C — Asymmetric Confined Capability-Lease Signing Authority"
slice: "ALA (foundational prerequisite for Q-C6-1)"
revision: 4
kind: "design-only (PREPARED_ONLY; DEFAULT-OFF; authorizes nothing)"
date: "2026-08-06"
author: "Claude Opus 4.8 (analysis)"
motivation: "rev2 binding re-review FAIL — the C2 scheduler-context issuer's trust model needs an asymmetric, confined lease authority that does not exist; capability leases are symmetric HMAC + a dev key minted in the owner-uid domain"
precedent: "scripts/ai/lib/execution_grant.py (R1_REVIEWED_PASS) — Ed25519, confined private key, tracked public verifier"
unblocks: "C2 scheduler-context issuer (rev3) → C6 → C4"
owner_directive: "2026-08-06 — 'asymmetric lease authority first'"
closes_review: "three binding reviews 2026-08-06: rev1 (2 HIGH)→rev2; rev2 (1 HIGH byte-equality)→rev3; rev3 REQUEST_REVISION — ORACLE CONFIRMED CLOSED, narrow text asks (codex-1 guard + 3 LOW)→rev4. rev1-3 superseded."
---

# Asymmetric Confined Capability-Lease Signing Authority

## Revision 4 — preserve the codex-1 revocation guard under the mint relocation (+ 3 precision corrections)

The rev3 binding re-review **CONFIRMED the signing-oracle is closed by construction** (mandate 2′
succeeds; the reviewer enumerated every first-party lease field — `capability_lease_gate.py:340-408`
— and found ZERO caller-influenced fields reach the signed lease). rev3's REQUEST_REVISION was narrow
text asks, added here; none reopens the oracle:

1. **[MED — HARD invariant, must be in frozen bytes] The gate RETAINS the codex-1 no-self-heal
   revocation guard.** `capability_lease.py`/`capability_lease_gate.py` forbid auto-reissue on an
   epoch bump ("Auto-reissue-on-bump would defeat revocation (C2-AMENDMENT codex-1) and is
   forbidden", gate docstring ~:46), enforced by the gate-side mint-once `_FIRST_PARTY_LEASE_CACHE`
   (`:326,354`) reissued ONLY via `reset_first_party_lease_cache()` (`:329-337`). Under rev3's mint
   relocation this MUST be preserved: the gate requests an authority-minted lease **once per
   cache-fill**, caches it, and does **NOT** re-request from the authority on an epoch bump — a
   cached lease goes stale at verify and is reminted only on a deliberate operator
   `reset_first_party_lease_cache()`. The authority is a STATELESS minter; revocation-durability
   stays a gate concern. Re-requesting per-call or on-bump = fail-open revocation = FORBIDDEN.
2. **[LOW] Epoch resolution moving gate→authority is intentional HARDENING, not "exact" identity.**
   Today the gate resolves the epoch (`:562`) and passes it to the minter (`:582`); rev3 has the
   authority resolve it itself (removing gate influence over the stamped `revocation_epoch`). Stated
   as a deliberate improvement, not identical behavior.
3. **[LOW] `issued_to` is PINNED to the constant `"switchboard-local-tool-executor"` (`:372`); the
   selector `caller-principal`/`task` are AUDIT-CORRELATION ONLY** and feed NO authority-bearing
   field. A future author must never wire `issued_to = caller-principal` (admission never keys on
   `issued_to`; it reads tool/risk/trust_tier from the verified lease).
4. **[LOW] Schema fields corrected:** the authority mints `input_schema: {}` / `output_schema: {}`
   (EMPTY constants, `:388-389`) — not "manifest-derived schemas." Wording fixed.

(rev3 mandate 2′ and rev2 mandates 1/3/4/5 stand as reviewer-confirmed. The oracle-closure crux is
settled; rev4 adds only the above clarifying text.)

## Revision 3 — the authority MINTS (selectors-only request), closing the rev2 oracle finding

The rev2 binding re-review confirmed scheme-pinning (mandate 1) and byte-parity/confinement/rotation
(mandates 3-5) are sound, but flagged ONE HIGH: mandate 2's "authority reconstructs the lease and
signs only if **byte-equal to the presented payload**" is unworkable, because three lease fields are
wall-clock and presenter-derived, NOT manifest-derivable — `issued_at = now`,
`expires_at = issued_at + TTL`, `lease_id = "first-party::{tool}::{issued_at}"`
(`capability_lease_gate.py:361-368`, verified). The authority's own clock never byte-matches the
gate's, so a whole-payload compare either always fails (spurious `payload-mismatch`) or must adopt
the gate's timestamps — re-opening the oracle (a compromised gate backdates/extends `expires_at`).

**Rev3 mandate 2′ (supersedes rev2 mandate 2):** the gate presents **SELECTORS ONLY** —
`{tool, caller-principal, task}` — NOT a signable payload. The authority is the SOLE minter: it reads
the manifest, resolves the epoch, and MINTS every field itself — the manifest-derived
`permissions/risk/trust_tier/zero_trust_behavior/schemas`, the authority-resolved `revocation_epoch`,
AND the temporal fields on its OWN clock (`issued_at = authority-now`,
`expires_at = issued_at + the one canonical FIRST_PARTY_LEASE_TTL`, `lease_id` derived from its own
`issued_at`). It then Ed25519-signs its own reconstruction and returns the complete signed lease.
There is NO caller-supplied payload to trust and NO byte-compare. A compromised owner-uid gate can
choose only *which* `{tool, principal, task}` to request — it cannot set an expiry, a permission, a
trust tier, or any field: it receives exactly the manifest-authorized lease with authority-minted
timestamps, or a typed deny (unknown tool / policy-refused). This makes "cannot forge past policy"
true by construction — the authority IS the policy and the minter.

(Rev2 mandates 1, 3, 4, 5 stand as reviewer-confirmed. Build-time note from the rev2 review: code
review MUST assert zero trust-rooted references to the legacy HMAC `verify()`; optionally have
`verify()` hard-reject `sig_scheme=="ed25519"` to remove the confusion surface — non-blocking,
fails closed either way.)

## Revision 2 — MANDATES closing the binding-review findings (rev1 must not be frozen)

The rev1 binding review returned REQUEST_REVISION: direction correct (closes offline-forgery +
key-theft), but two crux policies were left open and one (scheme-downgrade) was a confirmed exploit.
Rev2 makes them **MANDATES**, not options:

1. **[HIGH — scheme-downgrade, MANDATED closed] The authoritative verify entrypoint is scheme-PINNED
   to `ed25519` and NEVER verifies HMAC.** `capability_lease.py` gains TWO physically separate verify
   functions: `verify_authoritative(lease, keys_json)` — requires `sig_scheme == "ed25519"` as a
   REQUIRED SIGNED field, rejects absent/unknown/`hmac-sha256` with a typed deny, verifies Ed25519
   against `lease-signer-keys.json`, and has NO reachable dev-key/HMAC fallback; and the existing
   `verify()` (HMAC) — used ONLY by non-authoritative C1-shadow consumers. Every trust-rooted
   consumer (C2 issuer, C2 enforcement) calls `verify_authoritative` exclusively. A lease presented
   with `sig_scheme=hmac-sha256` (dev-key-forgeable) can NEVER pass an authoritative verify. This
   pinning lives in the PRIMITIVE, not downstream.
2. **[HIGH — signing-oracle, MANDATED closed via option (a)] The authority independently reconstructs
   the lease and byte-compares; the gate is pure transport.** `lease_signing_authority.py` does NOT
   sign an opaque presented payload. It reads the tool manifest (`_load_manifest()`) + resolves the
   epoch ITSELF, reconstructs the exact canonical first-party lease it would authorize for the
   requested `{tool, caller-principal, task}`, and signs ONLY if that reconstruction is byte-equal to
   the presented payload — otherwise typed `payload-mismatch` deny. A compromised owner-uid gate thus
   cannot obtain an over-broad lease: it can only get signed exactly what the authority itself would
   authorize from the manifest. This makes §2's "cannot forge past policy checks" TRUE.
3. **[MED — byte-parity, PINNED] Absent-field semantics.** `sig_scheme` is added to the signed
   canonical payload ONLY for `ed25519` leases. Flag-OFF (legacy) leases carry NO `sig_scheme` field
   → canonical bytes unchanged → exact byte-parity for every existing C0/C1/C2 lease + golden vector.
   Absent `sig_scheme` is treated as legacy-hmac by the C1-shadow `verify()` ONLY; the authoritative
   `verify_authoritative` REQUIRES `sig_scheme=ed25519` present (absent ⇒ deny). The two never share
   a default.
4. **[confinement threat-model, DOCUMENTED] The `0400`-cross-uid confinement holds against a
   compromised owner-uid PROCESS, not against the human owner's `sudo`/root** (the owner has setuid
   on this box and can read any `0400` file). This is the SAME envelope the accepted `execution_grant`
   precedent relies on; stated so it is not mistaken for a stronger guarantee.
5. **[rotation/revocation, PINNED] `key_id` is a REQUIRED SIGNED field; a missing/malformed
   `lease-signer-keys.json` ⇒ deny-ALL (never accept-all); revocation status is re-checked at EVERY
   verify (no cached-active past a status flip).**

The sections below are rev2 as amended by these mandates.

## 0. Why this slice exists

The rev2 binding re-review FAILed the C2 scheduler-context issuer because its authority — "verify a
presented Ed25519-signed C2 lease" — does not exist. Verified in code: `capability_lease.py:178`
signs with **symmetric HMAC-SHA256** (`:284` verifies with the same key), the key falls back to the
in-repo `DEV_SIGNING_KEY` (`:40,201`), and first-party leases are minted **in-process by the
switchboard as `cfg.primaryUser`** (`capability_lease_gate.py:397`). Symmetric ⇒ verify == forge, and
the secret sits in the same owner-uid domain as the shell the confinement excludes. No verifier can
be trust-rooted on such a lease.

This slice makes first-party capability leases **trust-rooted**: an Ed25519 private key held ONLY by
a confined signing principal (owner uid cannot read it), and any verifier holds only the non-secret
public key — so `verify != forge`. It mirrors the already-reviewed execution-grant R1 pattern
(`execution_grant.py`: `generate_keypair`, `sign` with a private key, `verify_signature(public_key)`;
the runner holds only the public key). It authorizes nothing; default-OFF.

## 1. Anchored baseline (verify at freeze)

| Operation | Path | Role |
|---|---|---|
| EDIT | `scripts/ai/lib/capability_lease.py` | Add an ASYMMETRIC path via TWO physically separate verify functions (rev2 mandate 1): `verify_authoritative(lease, keys_json)` requires `sig_scheme == "ed25519"` (a required signed field), rejects absent/unknown/`hmac-sha256`, verifies Ed25519 against `lease-signer-keys.json`, NO dev-key/HMAC fallback reachable; the existing HMAC `verify()` stays for non-authoritative C1-shadow ONLY. `sign_ed25519(payload, private_key)` mirrors `execution_grant.py`. `sig_scheme` is in the signed payload ONLY for ed25519 leases (legacy leases omit it → byte-parity, mandate 3). No verifier holds a private key. |
| EDIT | `ai-stack/switchboard/capability_lease_gate.py` | First-party lease issuance (`:397`), when `CAPABILITY_ASYMMETRIC_LEASE=1`, sends SELECTORS ONLY (`{tool, caller-principal, task}`) to the authority and receives a complete authority-minted, Ed25519-signed lease — it no longer constructs or signs the lease itself and never holds the Ed25519 private key. Flag OFF (default) = current in-process HMAC construction, exact byte-parity. |
| NEW | `scripts/ai/lib/lease_signing_authority.py` | The sole minter (rev3): receives SELECTORS ONLY (`{tool, caller-principal, task}`), authenticates the caller, reads the manifest + resolves the epoch, MINTS the complete canonical first-party lease itself (manifest-derived fields + authority-resolved epoch + authority-clock `issued_at`/`expires_at`/`lease_id`), Ed25519-signs its own reconstruction, and returns the complete signed lease. It never signs a caller-supplied payload; there is no byte-compare. Unknown tool / policy-refused ⇒ typed deny. Holds the private key via the confined service principal. |
| NEW | `nix/modules/services/lease-signing-authority.nix` | Dedicated default-OFF service `aq-lease-signing-authority`: own unprivileged user, SOPS Ed25519 private key read-only (`0400`, owned by this principal), UDS group-restricted + `SO_PEERCRED`, `NoNewPrivileges`, empty `CapabilityBoundingSet`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, no network. `enable=false`. switchboard.nix untouched (the gate is an outbound client). |
| NEW | `config/aqos/lease-signer-keys.json` | key-id → Ed25519 public verifier + `status∈{active,revoked}` + monotonic revision. **Sole** verifier source (public-only, no private material). Consumers (C2 issuer, C2 enforcement) verify against this. |
| EDIT | `config/env-contract.yaml` | `CAPABILITY_ASYMMETRIC_LEASE` default `0`; fixed non-overridable authority socket/key references. |
| NEW | `scripts/testing/test-asymmetric-lease-authority.py` | Offline: keypair, sign/verify round-trip, forged-signature reject, wrong/revoked key-id reject, `sig_scheme` dispatch, HMAC legacy parity, key-unavailable fail-closed, flag-OFF byte-parity, caller-cannot-forge (no private key outside the principal). |
| NEW | `scripts/testing/test-lease-signing-authority-service-coverage.py` | Integration: authority health + AQ-QA registration + dashboard projection. |
| EDIT | `scripts/testing/harness_qa/phases/phase0.py` | Register the integration AQ-QA check. |
| EDIT | `dashboard/backend/api/routes/aistack.py` + `assets/dashboard.js` | Live-backed authority state card. |

SOPS: add `lease-signing-ed25519-private-key` to `secrets/` + `secrets.nix`, decrypted to
`/run/secrets/…` `0400` owned by `aq-lease-signing-authority`. **HARD:** adding a key to `secrets.nix`
MUST be followed by `sops` re-encryption; never place private material in a tracked Nix file.

## 2. Trust model (the fix)

- **Confined signer:** the Ed25519 private key is readable ONLY by `aq-lease-signing-authority`
  (`0400`). The switchboard/gate (owner uid), a shell, `delegate-to-local`, and any owner-uid tool
  CANNOT read it. Signing happens only inside the authority.
- **Owner-uid gate presents SELECTORS ONLY; the authority is the SOLE MINTER (rev3 mandate 2′):**
  `capability_lease_gate.py` sends only `{tool, caller-principal, task}`. The authority reads the
  manifest, resolves the epoch, and MINTS the complete lease itself — manifest-derived fields,
  authority-resolved epoch, and authority-clock `issued_at`/`expires_at`/`lease_id` — then signs its
  own reconstruction. There is no caller payload and no byte-compare (which rev2 showed cannot hold
  against wall-clock fields). A compromised owner-uid gate can choose only *which* `{tool, principal,
  task}` to request; it cannot set an expiry, permission, or any field — it gets exactly the
  manifest-authorized lease or a typed deny. The gate never holds the private key, cannot mint
  offline, and cannot forge past the authority because the authority is both the policy and the minter.
- **Confinement threat-model (rev2 mandate 4):** the `0400`-cross-uid key confinement holds against a
  compromised owner-uid PROCESS, NOT against the human owner's `sudo`/root (setuid on this box). Same
  envelope as the accepted `execution_grant` precedent — stated, not a stronger claim.
- **Verifiers hold only the public key:** the C2 scheduler-context issuer, C2 enforcement, and any
  future reader verify with `config/aqos/lease-signer-keys.json`. `verify != forge`. This is the
  property the rev2 FAIL required and the property `execution_grant.py` already relies on.
- **Fail-closed:** private key unreadable/malformed ⇒ the authority denies signing (typed
  `signer-unavailable`); a verifier presented an `ed25519` lease whose key-id is unknown/revoked or
  whose signature fails ⇒ typed deny. No DEV-key fallback on the asymmetric path.

## 3. Migration and default-OFF boundary

`CAPABILITY_ASYMMETRIC_LEASE=0` (default): the gate signs HMAC in-process exactly as today
(byte-parity); the authority service is not enabled; verifiers accept the legacy `sig_scheme`. ON
(a later, separate owner act): first-party leases are Ed25519-signed by the authority;
`sig_scheme=ed25519` leases are the only ones the trust-rooted verifiers (C2 issuer) accept. The
C1 SHADOW/LOG-ONLY issuance path may remain HMAC (non-authoritative). Turning this ON does not by
itself enable the C2 issuer, C6, or C4 — each stays independently owner-gated.

## 4. Service Coverage (mandatory — ships an enabled-capable service)

1. Integration AQ-QA (`phase0.py`, hermetic): gate → authority sign → verify with public key, plus
   every deny (forged sig, revoked key-id, key-unavailable, flag-OFF parity).
2. Dashboard card: authority health, key availability, sign/deny counters by reason, latency
   buckets — low-cardinality; no lease content, key, or signature.
3. health-spider/alert: key-unavailable, forged-signature rate, unexpected signing while flag-OFF,
   service failure.

## 5. Downstream (folds the rev2 findings that belong to the issuer, not here)

Once this authority exists and is activated, the **C2 scheduler-context issuer rev3** must:
- verify the presented lease via `verify_ed25519` + `lease-signer-keys.json` (closes the rev2
  FAIL Finding 1);
- record a durable **consumed-lease ledger** and refuse a second mint per `{lease_id, grant_digest}`
  — the flagship Finding 2 AND the local-Qwen advisory both flagged one-lease-many-contexts; the
  issuer, not slot_queue, must enforce the 1:1 (closes Finding 2);
- bind `context.expires_at = min(lease.expires_at, cap)` and re-check the authoritative epoch at
  mint (closes Finding 3);
- fix the §2 bare-public-key reference (Finding 4).

## 6. Open blockers for the independent reviewer

1. **Signing-oracle — RESOLVED in rev3 (mandate 2′, selectors-only):** the gate presents only
   `{tool, caller-principal, task}`; the authority MINTS the entire lease (including the wall-clock
   temporal fields) and signs its own reconstruction — no caller payload, no byte-compare, so the
   rev2 temporal-field collision is gone. Reviewer to confirm the selector set carries no field that
   could widen authority (e.g., a caller-chosen TTL or permission), and that the authority's manifest
   + epoch resolution matches the gate's former `issue_first_party_leases` semantics exactly.
2. **Scheme-downgrade / blast radius — RESOLVED in rev2 (mandates 1+3):** authoritative verify is
   scheme-pinned to `ed25519` with no HMAC fallback; legacy leases omit `sig_scheme` (byte-parity).
   Reviewer to confirm no code path lets an authoritative consumer reach the HMAC `verify()`, and
   that the two verify functions cannot be confused at a call site.
3. **SOPS/secret ceiling:** exact `secrets.nix` entry, `/run/secrets` owner/mode, proof no owner-uid
   process can read the private key.
4. **Key rotation/revocation** via `lease-signer-keys.json` status + monotonic revision; fail-closed
   on unknown/revoked at verify.

## 7. Path

Independent binding review of these bytes → hash-bound freeze → single-use owner build activation →
default-OFF build + Service Coverage → independent code review → commit → separate owner flag-on.
THEN: C2 scheduler-context issuer rev3 (verifies asymmetric leases + consumed-lease ledger) → its
own review/freeze/build → C6 main freeze → C6 activation → C4 freeze.

`RECORD: PREPARED_ONLY asymmetric lease-authority design. No implementation, key material, service
enablement, signing, epoch bump, scheduling, provider traffic, deployment, or activation authority.`
