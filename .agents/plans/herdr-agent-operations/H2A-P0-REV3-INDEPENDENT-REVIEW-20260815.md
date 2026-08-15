---
doc_type: design-review
id: herdr-h2a-p0-rev3-independent-review-20260815
title: HERDR H2A-P0 revision 3 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
---

# HERDR H2A-P0 revision 3 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| schema | `1f5df849c9ab09ea7218967147d8f5c43c42d817c7c8cf4ef6d72c5ffe23ec87` |
| ledger | `774ec9f9fbcad805cbcda9fd51c14ae969d5389afc63855b9e88161244e524a4` |
| resolver | `496753ea6e2d6ebbf56a968100d6051597ed566f4f6782c79471dec05ada8e26` |
| fixture | `115cded60ad85bc80668696f47f6d989c35aea2ad0b4244bfede01e7564877e8` |
| test | `15f45adae4adceb145a26e722d48aa8a7360bad6f0a835b9b6f6b3b51835ebf9` |

Literal replay, insertion-independent canonicalization, full input binding, sampling/digest checks,
unavailable dependency semantics, Draft 2020-12 count pairing, all-fresh/unknown/through-parent truth,
empty controls, and purity passed. Acceptance still requires:

1. complete issuer-revision, subject-digest, expiry, revocation, replacement-binding, and actual
   supersession-cycle semantics;
2. restore `work[].progress_age` provenance to `agent_progress_facts` rather than canonical work input;
3. complete literal allowed-field traversal, malformed Unicode/control, realistic credential, and
   array-overflow privacy/bounds vectors.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — close reference lifecycle semantics, progress provenance, and literal privacy
matrix.
