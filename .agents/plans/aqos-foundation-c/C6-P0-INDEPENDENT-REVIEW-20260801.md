---
review_kind: "independent C6-P0 design review"
reviewer_role: "Codex independent reviewer"
subject: "C6-P0-TRUST-ANCHORS-DESIGN-20260801.md"
subject_sha256: "bce3a14b15d21f54279b31c80b43338ad6e2e39eab706ac7c7ffe3649acbfc8a"
reviewed_head: "17f899bf838973c755ab7a3e6095ec04a2e74220"
verdict: "REQUEST_REVISION"
implementation_authorization: "NONE"
activation_authorization: "NONE"
---

# C6-P0 Trust-Anchor Design — Independent Review

## Exact subject

Reviewed subject SHA-256:
`bce3a14b15d21f54279b31c80b43338ad6e2e39eab706ac7c7ffe3649acbfc8a`.
Its recorded base HEAD matches current HEAD
`17f899bf838973c755ab7a3e6095ec04a2e74220`.

The design direction is sound: C2 is named as sole issuer; the signed context
is domain-separated and peer-bound; raw caller context is denied; the owner-key
allowlist is public, immutable at runtime, and separated from the scheduler key;
and the future authority service remains disabled/default-OFF. It correctly
excludes live scheduling, epoch mutation, provider traffic, and premature
dashboard/AQ-QA claims. Deferring Service Coverage to the enabled authority
service is appropriate only because C6-P0 introduces no enabled service or
runtime capability.

## Freeze-blocking findings

1. **The inventory is not exact.** Two existing editable authority paths,
   `ai-stack/switchboard/capability_lease_gate.py` and
   `nix/modules/services/default.nix`, explicitly carry “re-pin before
   implementation” placeholders instead of current SHA-256 values. The table
   therefore cannot establish a candidate ceiling, owner authorization, or
   no-overlap check.
2. **Issuer identity remains a placeholder.** The document names “C2 admission”
   but not the exact existing issuer component path/hash, service principal,
   signer key revision, or authenticated transport peer identity. Those values
   decide who may mint a scheduler context and cannot be deferred while claiming
   an implementation-ready trust anchor.
3. **Service-hardening provenance is incomplete.** The proposed Nix source is
   correctly new/default-OFF, but the design does not identify the exact Nix
   import/evaluation path and current hashes that enforce its root-owned,
   non-writable key material. The inventory itself acknowledges this missing
   proof. Any such additional path would presently be unlisted.

## Verdict

**VERDICT: REQUEST_REVISION.** C6-P0 remains a useful PREPARED_ONLY design but
is not freeze-eligible. Replace all re-pin/identity/evaluation placeholders with
exact current paths, hashes, principals, key revision, and transport identity;
then re-freeze the complete inventory and obtain a fresh independent review.
No implementation, owner activation, runtime capability, Service Coverage
claim, staging, commit, network, provider, or deployment authority follows from
this review.
