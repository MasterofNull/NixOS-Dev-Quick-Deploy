---
doc_type: design-review
id: herdr-h2a-p0-rev1-independent-review-20260815
title: HERDR H2A-P0 revision 1 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
---

# HERDR H2A-P0 revision 1 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| `config/schemas/operator-context.schema.json` | `a1f9bf66b44b75cf9f8a872c7a773e6c7f087463b4aa3e77c87f9d6e9b6bf38d` |
| `config/operator-context-source-to-field-ledger.v1.json` | `ef3fda672224b723fff8d9c27f2e620949bd74cf681612ae8b1fa352d8cbd29f` |
| `scripts/ai/lib/operator_context_projection.py` | `b2402a078894507cbf742573e3cacdb0b2d7ed564de8309dbe39b990f4a67e9e` |
| `scripts/testing/fixtures/operator-context-golden.json` | `75cc4e1b38d5f6fb895aed276f50157b43451c68f415ab9b7a7e26054adbb26c` |
| `scripts/testing/test-operator-context-projection.py` | `d6e7574fd14669ae8457ee29a0e08a7e33da5fcbe92b7fe3e24d27be18e3a4cc` |

The five-file ceiling, closed shapes, structural ledger equality, empty controls, purity, and fixed output
SHA replay passed. Acceptance requires these revisions:

1. require and bind coherent `sample_id`, `sampled_at_bucket`, adapter revision/digest, uniqueness,
   skew, revocation, and supersession metadata; reject undeclared input;
2. expand the golden corpus to malformed/stale/conflict/unreadable sampling, exact input/output bytes and
   digests, complete R1–R7, reference collision/issuer/revocation/expiry/supersession/cycle, and privacy;
3. prevent fresh sources reducing to unknown and unknown/unavailable mission or learning counts becoming zero;
4. replace unrestricted required categories with closed enums, use exact named-envelope/versioned-pure-rule
   ledger sources, and enforce schema patterns/minimum lengths in the oracle.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — complete sampling/input binding, golden coverage, unknown semantics, and semantic
schema/ledger closure.
