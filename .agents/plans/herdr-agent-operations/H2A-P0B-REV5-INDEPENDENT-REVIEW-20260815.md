---
doc_type: design-review
id: herdr-h2a-p0b-rev5-independent-review-20260815
title: HERDR H2A-P0B revision 5 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_5_sha256: a000bac50fb663c4477227694a9632f5add52f0feb28565358062fad9e4f3cf8
---

# HERDR H2A-P0B revision 5 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| schema | `1de831f46eb0336c84e12e0f0616f6a9ba1a4b9f34ed3e3c4cc3663214ede5c3` |
| ledger | `2146cb869555aa118aa41d9ba251435daf47856b33ebf000f24ae010aa1c098a` |
| resolver | `96dfd67acdc0d4a427001715fa5cf37eac5082c43bd9c07f451c5ad885b8bc5f` |
| fixture | `f77b56aeaca616c145827df5bd6c360b3672139414621971cf4579652d68d05c` |
| test | `918b5b9f303dcb9dfee03347e02277ebaad3fd3995d4b572a59205a5dafd8427` |

Complete unauthorized-input binding, static closure, pane truth, credential rejection, duplicate projected
refs, 82-leaf parity, sampling/replay/schema checks, and purity passed. Acceptance still requires:

1. require active/unexpired/non-superseded lifecycle for every emitted ref;
2. bound issuer/expiry, reject duplicate bindings, require replacement targets/subject binding, and detect cycles;
3. correct session/pane expected-field ledger provenance;
4. derive coverage across every configured/runtime/socket/session/version/protocol/pane/layout/count/
   reconciliation dimension.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — close lifecycle enforcement/graph validation, provenance, and full coverage.
