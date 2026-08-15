---
doc_type: design-review
id: herdr-h2a-p0b-rev8-independent-review-20260815
title: HERDR H2A-P0B revision 8 independent review
status: complete
reviewed_at: 2026-08-15T19:32:35Z
reviewer: Gibbs
reviewer_role: independent-reviewer
verdict: REQUEST_REVISION
runtime_authority: false
---

# HERDR H2A-P0B revision 8 independent review

## Exact reviewed subject

- schema: `1de831f46eb0336c84e12e0f0616f6a9ba1a4b9f34ed3e3c4cc3663214ede5c3`
- ledger: `89e358a6284bda789db5571ab105a5b8040b487a0b56486d954ac409624813d8`
- resolver: `4af0cf05122c3f6ba9a881a489ce9aabc5ddde6a609f1dcc81f2d406b0dc8dbf`
- fixture: `7847e4a399d616b75f9a03446bd54d5ad65a1e2ac92f0b27594d83901a39947c`
- test: `0f41812beaa138b76de0c1325ddc524dac8d3c4b4aa552660090a44c8d7e23da`

The hashes matched. Canonical mapping-order independence, authorized-path dimension coverage, cycle-specific rejection, 82-leaf parity, Draft 2020-12 validation, literal replay, lifecycle/privacy/bounds, and pure operation passed.

## Blocking invariant

`coverage_totality`: no-adapter, unauthorized, stale/conflict, and missing-observation returns bypassed the complete reducer. Emitted dimensions were predominantly unknown while the coverage summary counted only one unknown, so branch coverage was false. The authorized-only oracle did not cover these return classes.

No repository or runtime mutation occurred.

VERDICT: REQUEST_REVISION — apply one complete coverage reducer to every return class and assert branch-table equality; recurrence after this contract-level repair must escalate rather than replay.
