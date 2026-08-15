---
doc_type: design-review
id: herdr-h2a-p0b-rev2-independent-review-20260815
title: HERDR H2A-P0B revision 2 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_5_sha256: a000bac50fb663c4477227694a9632f5add52f0feb28565358062fad9e4f3cf8
---

# HERDR H2A-P0B revision 2 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| `config/schemas/herdr-presentation.schema.json` | `1de831f46eb0336c84e12e0f0616f6a9ba1a4b9f34ed3e3c4cc3663214ede5c3` |
| `config/herdr-presentation-source-to-field-ledger.v1.json` | `7a582b3154c1019c6bd1cbe913fd309ab89d7e8f355657cc00e74fe7cbcd396f` |
| `scripts/ai/lib/herdr_presentation_projection.py` | `47c101ad2a5ea70d9aba885f1d2bb86cf8850bfa83d5b06b4e4553aee60c6e3d` |
| `scripts/testing/fixtures/herdr-presentation-golden.json` | `acb60c7736c9c115bcf70c0175710c5c7ef2cabe97bda13496ec17064a773a71` |
| `scripts/testing/test-herdr-presentation-projection.py` | `35ba8e43a90533c687dedb99e8113484337467332152a547358c3e9511407f7c` |

Literal replay, schema structure, count/reference constraints, purity, and five golden projections passed.
Acceptance still requires:

1. exact Contract #5 validation in the resolver and test oracle for every dimension;
2. static expected provenance that authorized observation cannot overwrite;
3. mandatory coherent sampling/policy metadata and rejection of undeclared input;
4. explicit reconciliation of the claimed 86-rule count with the actual exact Contract #5 leaf set;
5. malformed/unreadable dimension, reference lifecycle, bounds, credential/control-character, and privacy regressions.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — close validation, provenance, sampling, leaf-count, and regression gaps.
