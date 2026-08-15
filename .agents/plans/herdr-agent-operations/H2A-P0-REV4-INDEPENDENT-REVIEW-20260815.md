---
doc_type: design-review
id: herdr-h2a-p0-rev4-independent-review-20260815
title: HERDR H2A-P0 revision 4 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
---

# HERDR H2A-P0 revision 4 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| schema | `1f5df849c9ab09ea7218967147d8f5c43c42d817c7c8cf4ef6d72c5ffe23ec87` |
| ledger | `aa88adad19a58c4bd47f793449251b5cfaad9d4ff20a51951b66414d56db2dff` |
| resolver | `8674b1b58097dd5004fb22796ce35ece92c6f060ea7e193f4f016e1479defa2c` |
| fixture | `fc651b227a34072b2ee5d7f374c099e3da9175c769d0458670a05da3a309474e` |
| test | `b52b20257af9b557ea3aa41cf8c30f9b62d85684ac34ad91ef81f96ac1f346d3` |

Reference identity/expiry/replacement/cycle checks, resolver-side progress authority, literal replay/privacy,
sampling/input binding, count/unknown truth, non-echo errors, empty controls, and purity passed. Acceptance
still requires:

1. correct ledger provenance for mission objective and progress age;
2. prevent superseded envelopes from projecting current/fresh facts;
3. verify the declared supersession chain against the actual replacement graph;
4. add literal work/attention/progress/lifecycle-chain overflow vectors and allowed-field shell/credential cases.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — close ledger provenance, superseded authority, chain evidence, and overflow matrix.
