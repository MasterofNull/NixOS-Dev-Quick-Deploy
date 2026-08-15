---
doc_type: design-review
id: herdr-h2a-p0-rev2-independent-review-20260815
title: HERDR H2A-P0 revision 2 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-15
inventory_commit: 919410584a74cea04f16ebbcdb36c923b74fd692
contract_zero_sha256: 716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48
---

# HERDR H2A-P0 revision 2 independent review

## Exact subjects

| Subject | SHA-256 |
|---|---|
| schema | `f970e335c3597bde460fd85b6ee36a2584bc6a6ab11eb24b0af29ca7e3274c9a` |
| ledger | `016e69a82069566210754146cd259fe81488ce207d6ed185957cbe064843c404` |
| resolver | `7004363a6a7ce6418e3688bbc13c1780b2f2c1b43263d2e5fffaf7495f0ac637` |
| fixture | `6d70a247cd5bde2803f3001dc34d89c9bdcc3827541f6364739037be52682a2a` |
| test | `0c4ec324c2221197c898823431fb72c4ee6e78ee4b14aa8acd3bb8821433f552` |

Named closed envelopes, all-fresh reduction, happy-path unknown counts, leaf/source parity, empty controls,
and purity passed. Acceptance still requires:

1. replace fixture replay `TBD` values with literal normalized-input and output bytes/digests;
2. prevent unavailable review/learning envelopes from supplying accepted or known-zero dependent facts;
3. enforce count state/value pairing in JSON Schema;
4. canonicalize semantically equal input mappings independent of insertion order;
5. enforce digest uniqueness and full issuer/subject/expiry/replacement/supersession-cycle reference lifecycle;
6. supply literal rejection inputs for the complete privacy/metadata/reference matrix and align
   `work[].progress_age` ledger provenance with the resolver.

The reviewer made no repository modification or runtime action.

VERDICT: REQUEST_REVISION — finish literal replay, dependency semantics, schema pairing, canonical input,
reference lifecycle, and the rejection matrix.
