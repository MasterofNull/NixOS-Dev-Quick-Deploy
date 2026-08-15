---
doc_type: design-review
id: herdr-h2a-p0b-rev3-independent-review-20260815
title: HERDR H2A-P0B revision 3 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_5_sha256: a000bac50fb663c4477227694a9632f5add52f0feb28565358062fad9e4f3cf8
---

# HERDR H2A-P0B revision 3 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| schema | `1de831f46eb0336c84e12e0f0616f6a9ba1a4b9f34ed3e3c4cc3663214ede5c3` |
| ledger | `2146cb869555aa118aa41d9ba251435daf47856b33ebf000f24ae010aa1c098a` |
| resolver | `3fe5343983e1ba96cbaa966c6b1381321854af265b8e67514fe498e62f01d732` |
| fixture | `5572c81654f0ba4c7a007f0748ca0e78213b8615578f50cabf525be457d92eb6` |
| test | `eb3cad7b107171e56ae590b3c7d034223aea1582f463a85cb9e70badd198eac7` |

The exact 82-leaf Contract #5 profile, ledger parity, fixed replay, Draft 2020-12 output/count/reference
checks, sampling requirement, static-observation key separation, max-64 bound, and purity passed. Acceptance
still requires:

1. close and bind every `static_expected` key;
2. correct session/pane expected provenance and derive coverage rather than accepting observer counts;
3. reject duplicate refs and false compatible/match states with missing identities;
4. implement genuine issuer/subject/expiry/replacement/cycle lifecycle validation;
5. reject realistic credential-shaped tokens and add per-dimension malformed/privacy regressions.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — close static input, provenance, semantic truth, lifecycle, and privacy gaps.
