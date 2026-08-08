---
title: "Foundation C — ALA→C2-SCI signed admission-contract and epoch repair"
slice: "ALA-C2-R1"
date: "2026-08-08"
status: "PREPARED_ONLY — owner chose the strong signed-tuple direction; implementation requires independent design PASS and exact-hash activation"
kind: "bounded corrective design"
base_head: "0579c5796730c443bca31612efa8e4aa6ce784b3"
evidence:
  - ".agents/plans/aqos-foundation-c/CATCHUP-CODEX-CONFIRMATORY-AUDIT-20260808.md"
  - ".agent/memory/issues-backlog.md#c2-sci-HIGH-ala-lease-schema-mismatch-activation-blocker"
---

# ALA→C2-SCI contract repair

## 1. Owner direction and objective

The owner directed the program to follow the recommended strong-contract fork: the confined
Asymmetric Lease Authority (ALA) must mint `grant_digest` and `policy_revision` as fields inside the
Ed25519-signed lease. C2-SCI must retain both fields in its admission tuple and retain the durable
single-use key `{lease_id, grant_digest}`. Dropping either C2 requirement is rejected because it weakens
the signed admission and replay boundary.

This slice corrects two activation blockers found by a real producer→consumer probe:

1. real `mint_first_party_leases()` output lacks both signed fields and is rejected by
   `mint_scheduler_context()` as `lease-fields-malformed`;
2. issuer epoch handling accepts a signed future epoch and maps unavailable/malformed epoch state to
   `0` instead of denying.

All affected services and flags remain default-OFF. This packet authorizes no implementation, service
start, key operation, network/provider call, traffic, deployment, flag flip, staging, or commit.

## 2. Binding contract

### 2.1 Manifest revision

`config/first-party-tools.json` remains the owner-controlled policy SSOT. Its existing top-level
`version` is the integer `policy_revision`. A missing, boolean, non-integer, non-positive, or otherwise
malformed version makes the ALA manifest unusable and minting returns a typed deny/empty set; it never
substitutes `0` or `1`. Every authority-changing manifest edit must increment this version. The manifest
is verify-only in this slice; changing it is a stop condition.

### 2.2 Policy-binding digest

For each tool, ALA constructs the domain-separated projection
`aq.first-party-policy-binding/1` containing exactly:

- `tool`;
- `policy_revision`;
- stable authority identity: `source`, `owner`, `issued_to`, `cost_class`, `parent_lease_id`;
- the complete manifest-derived authority fields: `permissions`, `input_schema`, `output_schema`,
  `trust_tier`, and `zero_trust_behavior`.

The projection excludes `lease_id`, `issued_at`, `expires_at`, `revocation_epoch`, `issuer_key_id`,
`sig_scheme`, and `signature`; clock, lease identity, epoch bumps, and key rotation therefore do not
silently redefine policy identity. Canonical bytes are UTF-8 JSON with sorted keys, compact separators,
`ensure_ascii=False`, `allow_nan=False`, and NFC-normalized strings recursively. `grant_digest` is the
lowercase SHA-256 hex digest of the domain tag, one NUL byte, and those canonical bytes. The grammar is
exactly `^[0-9a-f]{64}$`.

ALA inserts `policy_revision` and `grant_digest` before `capability_lease.sign_ed25519()`; therefore both
are covered by the existing lease signature. It does not change global `canonical_payload()` and does
not change legacy HMAC lease bytes when `CAPABILITY_ASYMMETRIC_LEASE=0`.

### 2.3 C2 consumption and schema

C2-SCI continues to re-derive the admission tuple only from verified signed lease fields. It requires
`policy_revision` to be a positive non-boolean integer and `grant_digest` to match the exact lowercase
64-hex grammar before any durable ledger mutation.

`config/schemas/scheduler-lease-context.schema.json` is corrected to the actual closed signed producer:

- require `schema="aq.scheduler-lease-context/1"`;
- require integer `schema_version=1`;
- require `trust_tier` and `sig_scheme="ed25519"`;
- require integer `policy_revision>=1`;
- require lowercase 64-hex `grant_digest`;
- keep `additionalProperties:false` and every existing audience/identity/time/epoch/signature field.

The producer is fixed to the reviewed schema; the schema is not widened to accept ambiguous variants.

### 2.4 One epoch authority, exact comparison

ALA and C2-SCI stop reading the tracked genesis file as a live authority and stop using any
failure-to-zero/environment-epoch fallback. Their confined service wrappers use
`revocation_epoch.resolve_current_epoch()` over `AQ_REVOCATION_EPOCH_SOCKET_PATH`, backed by the existing
read-only operation on `aq-revocation-epoch-authority`. Missing/unreachable/denied/malformed responses are
typed denies before lease or scheduler-context minting. The ALA and C2 service bundles include only the
already-built `revocation_epoch.py` and `revocation_epoch_transport.py` client dependencies; their service
principals receive connect-only membership in `aq-revocation-epoch-clients`. They receive no access to the
authority StateDirectory and no epoch-write authority.

`mint_scheduler_context()` requires the verified signed lease's `revocation_epoch` to equal
`current_epoch` exactly. Both past and future values deny with `lease-epoch-mismatch`; `<` and `0`
substitution are prohibited.

## 3. Exact implementation ceiling

The correction may edit only these twelve files, from these exact predecessor hashes:

| Path | SHA-256 | Purpose |
|---|---|---|
| `scripts/ai/lib/lease_signing_authority.py` | `f1ad321dce3c4df81fbf665a40d51beb83680fa596dc33af0ad8d6fd8ca34c1f` | manifest revision, canonical policy digest, signed fields, strict authority reader |
| `scripts/ai/lib/scheduler_context_issuer.py` | `de21c748d45bcaf6d431527e09dcae92c289f3c268500f8d53a6227323a7a4b2` | exact epoch equality and strict signed-field grammar |
| `scripts/ai/lib/scheduler_context_transport.py` | `3d55b25313243c9705bbbba73659ef8a8641e1c49542e81000006ba02496d78e` | strict UDS epoch resolution; no file/zero fallback |
| `config/schemas/scheduler-lease-context.schema.json` | `be3149102b1bdd02275a33f529f5bcb8e0f2fc3761c69b198751b1c5018b3d49` | producer/schema parity |
| `nix/modules/services/lease-signing-authority.nix` | `f3cee4f24c344ebcc6f28fe816a0cdc1c98384f176043099e51b92d8baa16ca3` | client bundle, socket path, connect-only group |
| `nix/modules/services/c2-scheduler-context-issuer.nix` | `f63d3f74a29c261b38f8f8e2978f8e5182002d9a4d244be97523f1d5fb2ef557` | client bundle, socket path, connect-only group |
| `config/env-contract.yaml` | `74c10eb277d72c06719fd05fe2dc10564dbb7443c66d4583158b93c733860b98` | declare the shared epoch-authority socket variable and retire live epoch-file inputs |
| `scripts/testing/test-lease-signing-authority.py` | `588929dfc5d0f528e636fb63029b0f5857b0d494243a14055c7a262a1d14d0da` | digest/revision/signature/legacy-parity vectors |
| `scripts/testing/test-scheduler-context-issuer.py` | `39f6ff542bfce1fc1be4a942fb5b13f0b4cbe9b1dd2cd28fb8f22474158734cb` | real ALA→C2 seam and exact epoch vectors |
| `scripts/testing/test-c2-gate-dispatch-wiring.py` | `b53962fc21df9b8c4e199373a993149d3a6ba654017ab1dca6c6916103212d82` | signed tuple propagation and schema-consumer negatives |
| `scripts/testing/test-c2-sci-service-coverage.py` | `b74fc49d9434ea891473e1d8f88405e18afe3f6c4c6741ea9dd72eb42d8d7e8a` | service bundle/env/default-OFF/monitoring contract |
| `scripts/testing/test-scheduler-context-ledger.py` | `7eec12dd270cacf6ea12de57aed9d3ffeedc4152ad64999b66d72f647c3d23f1` | retain durable `{lease_id,grant_digest}` replay and race coverage |

Verify-only no-touch anchors:

- `config/first-party-tools.json` `a17650f228b4ff17068b9e426f2bf2b5a8495aaa60d66683aac620e0a11a4e8d`;
- `scripts/ai/lib/revocation_epoch.py` `d6c3a3b60a04fde15b5fe9a619f6fc290110776bbdefc35c6de21dcd594a75e6`;
- `scripts/ai/lib/revocation_epoch_transport.py` `066b30c326898d6ef8e4ab085cf82ce131bb9812b08a61993de86b0812a6be28`;
- existing dashboard/Phase-0 projections: `aistack.py` `aa855d617f13fa5522b53a0ae5c62aa8224b9b5e4712e513a98b3843bb8526be`,
  `assets/dashboard.js` `9c892841879c52fdcfe2281021b652812e7e4d4be16243623e80987ae7129a04`,
  `phase0.py` `5e6f22088cf93315a27b7a0809e51145ccdee7cac70a888f35b7db154ea6b6d1`.

Any need to edit the manifest, revocation authority, capability gate, switchboard, dashboard, Phase-0,
secrets, keys, deployment, or another file is a stop condition and requires a new slice.

## 4. Acceptance evidence

The implementation candidate must prove, offline and without live services/providers/network:

1. real `mint_first_party_leases()` output passes directly to `mint_scheduler_context()` with no
   hand-added fields and yields a schema-valid signed context;
2. same policy at different mint times, epochs, lease IDs, and active key IDs has the same policy digest;
   every authority-field or manifest-revision mutation changes it;
3. `policy_revision` and `grant_digest` tampering invalidates the lease signature;
4. legacy HMAC/default-OFF lease canonical bytes and call trace remain unchanged;
5. missing/malformed manifest revision denies; malformed digest/revision denies before ledger mutation;
6. past epoch, future epoch, missing socket, authority deny, malformed response, and malformed durable
epoch store all deny without returning or substituting `0`; ALA exposes a distinct bounded
   `epoch-authority-unavailable` outcome rather than conflating authority failure with a valid empty manifest;
7. exact epoch succeeds; replay/race tests retain exactly one ledger winner;
8. every minted scheduler context validates under Draft 2020-12 against the corrected closed schema;
9. both Nix service bundles include the strict client dependencies, preserve default-OFF, preserve
   `RestrictAddressFamilies=[AF_UNIX]`, inject the epoch-authority socket, grant only client-group socket
   connect—not StateDirectory/key widening—and contain no live epoch-file fallback;
10. focused suites, Python compile, JSON parse/schema checks, Nix parse, full existing C2/ALA regressions,
    and Tier-0 pass before any commit proposal.

An independent flagship reviewer must issue PASS on the exact candidate manifest. The implementer cannot
review itself. No activation or deployment is part of acceptance.

## 5. Sequencing

This repair may be implemented independently of the halted C6-B3 live handoff because it corrects the
producer/issuer contract while all flags remain dormant. It does not unblock C6 activation by itself:
C6-B3 still requires a separately re-frozen authenticated dispatch handoff and immediately-pre-provider
epoch fence, followed by B4 Service Coverage.

`RECORD: PREPARED_ONLY. Strong signed-tuple direction selected; implementation awaits independent design review and exact owner activation.`
