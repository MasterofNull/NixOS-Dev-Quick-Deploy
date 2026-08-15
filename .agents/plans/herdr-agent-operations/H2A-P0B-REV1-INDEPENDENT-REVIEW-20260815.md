---
doc_type: design-review
id: herdr-h2a-p0b-rev1-independent-review-20260815
title: HERDR H2A-P0B revision 1 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_5_sha256: a000bac50fb663c4477227694a9632f5add52f0feb28565358062fad9e4f3cf8
---

# HERDR H2A-P0B revision 1 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| `config/schemas/herdr-presentation.schema.json` | `fcb1363b93e77915eeac4a0dd6ccd4c519bda10a1294f83afc1bc11b0697aab9` |
| `config/herdr-presentation-source-to-field-ledger.v1.json` | `8af74c3ebb1520c48cf75d9e52f4575ba769fbb8aff4c9081d70d3d8d59325e1` |
| `scripts/ai/lib/herdr_presentation_projection.py` | `b2c606b8d41f1ee4290466f2b18af9ecdedd73972fe45bfd8388636c067e1868` |
| `scripts/testing/fixtures/herdr-presentation-golden.json` | `df037a2e5e8c57044d2eb03d340c0c04c288c9adf68de3bf18fec1da0e9e51d7` |
| `scripts/testing/test-herdr-presentation-projection.py` | `08eeaa55f6ebd64fee749f43561e397a767e1f64f8b374970d32261e8b7ce6dc` |

The hermetic suite passed five tests, but its acceptance coverage was insufficient. Required revisions:

1. support every Contract #5 authorized normalized observation dimension without adapter or I/O;
2. enumerate exactly one ledger rule per schema leaf and test both set differences plus duplicates;
3. enforce count null/state pairing and non-null required references in JSON Schema;
4. freeze exact canonical bytes/digests and add complete schema, parity, privacy, bounds, and reference vectors;
5. implement the inventory sampling/coherence envelope and complete-input digest binding.

The pure/no-runtime boundary, exact five-file ceiling, and subject hashes passed. The reviewer made no
repository modification.

VERDICT: REQUEST_REVISION — complete the normative resolver, leaf ledger, schema invariants, sampling
contract, and golden/privacy acceptance matrix.
