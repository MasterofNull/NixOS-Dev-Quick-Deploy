---
title: "Foundation C — ALA→C2 contract repair implementation authorization"
slice: "ALA-C2-R1"
date: "2026-08-08"
status: "PREPARED_ONLY — NOT ACTIVE"
kind: "single-use hash-bound authorization template"
design: ".agents/plans/aqos-foundation-c/ALA-C2-CONTRACT-REPAIR-DESIGN-20260808.md"
base_head: "0579c5796730c443bca31612efa8e4aa6ce784b3"
---

# Prepared authorization

This record is inert until the owner activates its exact SHA-256 after the design receives an independent
flagship PASS. Activation assigns a named temporary-candidate preparer, a distinct repository implementer,
and a distinct independent flagship reviewer for the exact twelve-file ceiling and verify-only anchors in
the bound design. It also names one exclusive lease identifier covering the complete source, temporary
candidate, protected worktree, index, validation, manifest, and commit-owner boundary.

The implementation sequence is mandatory:

1. preflight the full HEAD `0579c5796730c443bca31612efa8e4aa6ce784b3`, empty protected index, all
   predecessor/no-touch hashes, active authorization hash, and absence of an overlapping writer;
2. prepare the complete twelve-file candidate under one named `/tmp` root without changing repository bytes;
3. obtain independent exact-byte review of that temporary manifest;
4. only after temp PASS, apply exactly those reviewed bytes to the twelve repository paths; the exclusive
   lease begins on the first repository write and expires no later than 45 minutes afterward;
5. recheck no overlap and empty index, run focused offline validation, then run Tier-0 only in a disposable
   clone/worktree whose index and runtime-only evidence are isolated from the protected repository;
6. recheck protected HEAD/index/no-touch/inventory bytes, freeze the exact candidate manifest, and obtain a
   final independent flagship verdict before releasing the lease.

Permitted after activation only: temporary preparation; repository implementation within the exact twelve
paths after temp PASS; offline focused tests; Python/JSON/Nix validation; isolated disposable-clone Tier-0;
exact manifest creation; independent read-only review. Tier-0 may not stage or mutate the protected index,
candidate inventory, or primary repository state.

Prohibited: any thirteenth path; manifest/revocation-authority/capability-gate/switchboard/dashboard/Phase-0
edit; secrets or key operations; database; live service/socket/provider/network traffic; flag flip;
deployment/rebuild; staging; commit; push; destructive Git; history rewrite; self-review; or normalization of
a failed test/review. Stop on non-empty protected index, HEAD, predecessor, no-touch, inventory,
authorization, candidate, lease-expiry, or overlap drift. A pause requires full revalidation before another
write; an expired lease cannot be extended narratively and requires a fresh owner activation.

The activation is single-use and does not authorize C2-SCI or C6 activation. A later release authorization
is required for staging/commit, and a later owner act is required for any runtime enablement.

`RECORD: PREPARED_ONLY. No implementation authority until exact-hash owner activation.`
