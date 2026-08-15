---
doc_type: design-review
id: herdr-h2a-p0b-rev7-independent-review-20260815
title: HERDR H2A-P0B revision 7 independent review
status: complete
reviewed_at: 2026-08-15T19:14:47Z
reviewer: Gibbs
reviewer_role: independent-reviewer
verdict: REQUEST_REVISION
runtime_authority: false
---

# HERDR H2A-P0B revision 7 independent review

## Exact reviewed subject

- `config/schemas/herdr-presentation.schema.json`: `1de831f46eb0336c84e12e0f0616f6a9ba1a4b9f34ed3e3c4cc3663214ede5c3`
- `config/herdr-presentation-source-to-field-ledger.v1.json`: `89e358a6284bda789db5571ab105a5b8040b487a0b56486d954ac409624813d8`
- `scripts/ai/lib/herdr_presentation_projection.py`: `87b903e731ea0525e8d944506c1cbde76aeb5df7dce293f1fca929a6e14d888c`
- `scripts/testing/fixtures/herdr-presentation-golden.json`: `e9bbc51c241d989351881da989f3ae2c540339e79a5adf369ab9719e38f34771`
- `scripts/testing/test-herdr-presentation-projection.py`: `fb063ed9bc4c8e75d1c4103cbf35a2bbd78aa22d24530e2103f1d9044db1b407`

The submitted hashes matched the reviewed bytes.

## Blocking findings

1. Canonical bytes remain insertion-order dependent. `canonical_bytes()` uses unsorted mapping keys and some normalized structures preserve caller key order. Reversing input mappings produced an equal projection object but different canonical bytes and SHA-256; the replay oracle repeats only the original insertion order.
2. Coverage is incomplete and can be semantically false. It omits observer state and socket subdimensions, session detach state, pane freshness, and pane observation delta. A targeted change of `socket.peer` from `reachable` to `unknown` preserved the unknown output but still reported `coverage = {known:17, unknown:0, unavailable:0}`.

## Verified gates and note

The reviewer confirmed closed expiry categories; literal normalized lifecycle negatives for past expiry, missing replacement, subject mismatch, exact duplicate, and a two-node cycle; exact 82-leaf ledger parity and expected provenance; complete-input hashing; Draft 2020-12 output validation; count pairing; authorization/static-observed separation; bounded references and arrays; pane-match truth; credential/path/control rejection; and the pure no-I/O/no-runtime boundary. The hermetic suite passed 11 tests.

The two-node cycle is fail-closed but currently rejects through `reference_replacement_target_invalid`, so it does not exercise the cycle-specific rejection branch.

The reviewer made no repository modification and performed no staging, commit, activation, runtime, or HERDR operation.

VERDICT: REQUEST_REVISION — make canonical serialization mapping-order independent and derive coverage from every required observer, socket, session, pane, layout, and health subdimension.
