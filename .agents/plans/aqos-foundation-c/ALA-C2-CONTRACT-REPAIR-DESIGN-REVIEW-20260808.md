---
title: "ALA→C2 contract repair — independent flagship design review"
date: "2026-08-08"
reviewer: "codex-subagent-l3a_inventory_freeze_audit"
role: "independent flagship design reviewer"
status: "PASS"
base_head: "0579c5796730c443bca31612efa8e4aa6ce784b3"
---

# Independent review record

## Exact reviewed subjects

- Design: `ALA-C2-CONTRACT-REPAIR-DESIGN-20260808.md`, SHA-256
  `3c7c0e7f672b8a55e65ed37a7cea0dd87ae189af6e352fc7fb09ea88032dc497`.
- Prepared authorization: `ALA-C2-CONTRACT-REPAIR-AUTHORIZATION-20260808.md`,
  SHA-256 `ee3dc163cbe88b82f2268c69a3251c04aa55f96721fe616d2cec2cad8e495369`.

Both hashes and the full bound HEAD were rechecked before this record. The
reviewer did not author or alter either reviewed subject.

## Criteria and findings

1. **Signed authority contract — PASS.** ALA mints owner-policy-derived
   `policy_revision` and domain-separated `grant_digest` before Ed25519
   signing; C2 retains the signed admission tuple and `{lease_id, grant_digest}`
   single-use ledger. The repair closes the real minter→issuer shape mismatch
   without weakening replay protection.
2. **Canonicalization and compatibility — PASS.** Digest inputs, exclusions,
   NFC/UTF-8 compact canonical JSON, `allow_nan=False`, and lowercase digest
   grammar are explicit. Global lease canonicalization remains untouched, so
   default-OFF legacy HMAC bytes retain their parity boundary.
3. **Epoch threat model — PASS.** The repair replaces permissive file/zero
   fallback with confined epoch-authority UDS resolution, typed
   `epoch-authority-unavailable`, connect-only group access, and exact
   lease/current epoch equality. Both future and stale epochs deny.
4. **Closed schema and test evidence — PASS.** The planned schema corrects
   current producer drift while keeping `additionalProperties:false`. Required
   evidence includes a real ALA minter→C2 issuer seam, signature tampering,
   digest/revision mutation, schema validation, epoch negatives, replay/race,
   and service bundle/no-fallback checks.
5. **Scope and composition — PASS.** The twelve-file ceiling and no-touch
   anchors prevent manifest, epoch-authority, gate, dashboard, Phase-0, key,
   deploy, and C6-B3 handoff changes. The repair remains default-OFF and does
   not claim C6 activation.
6. **Authorization safety — PASS.** It requires named distinct temporary
   preparer, repository implementer, and reviewer; mandatory temp-first exact
   manifest PASS; pre/post empty-index and no-overlap checks; an exclusive
   source/worktree/index/commit-owner lease expiring within 45 minutes after
   first repository write; and isolated Tier-0 that cannot mutate protected
   repository state. Staging, commit, runtime, network, deployment, key, and
   flag operations remain prohibited.

## Boundary

This is a design-only PASS. It does not activate the authorization, grant a
lease, authorize implementation, or accept a future candidate. A separately
named owner activation and independent exact-byte candidate review remain
required.

VERDICT: PASS — exact design and inactive authorization satisfy the bounded, fail-closed ALA→C2 repair criteria.
