---
doc_type: design-review
id: herdr-h2a-rev4-independent-review-20260814
title: HERDR H2A revision 4 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (independent aq_reviewer)"
verdict: PASS
date: 2026-08-14
---

# HERDR H2A revision 4 independent review

This is the binding, read-only acceptance review of the five-document H2A `PREPARED_ONLY` design
candidate. It grants no implementation, staging, commit, rebuild, HERDR runtime, deployment, or
activation authority, and it does not waive the accepted-H1 predecessor gate.

## Exact accepted subjects

| Subject | SHA-256 |
|---|---|
| `H2A-IMPLEMENTATION-INVENTORY-20260808.md` | `838f2c4edd9c1b51543180d2d4ca60cc00170444d9adc8b45008a3317d5fed91` |
| Contract #2, operator context to layout planner | `8074632c4b73dbc37c4da98533a703c12af441ac37f3274e914232563de1ead5` |
| Contract #3, operator context to web dashboard | `f407bafeb12ad85a95a95a88406a5cf2e1a73d68622844aa104d23c9929ac9c7` |
| Contract #4, human controls to audited AQ actions | `b8cedf3b50e857bb5da028823dc94bc655deb4a4125f867498fc6778c3775f08` |
| Contract #5, HERDR observation to presentation health | `a000bac50fb663c4477227694a9632f5add52f0feb28565358062fad9e4f3cf8` |
| Contract zero | `716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48` |

All subjects were untracked and unstaged at review time.

## Acceptance evidence

- `count_state` is exactly `known|unknown|unavailable` and is used consistently for both session
  counts and every `counts.*` member; generic non-count state remains separately defined.
- Operator context and HERDR presentation remain independent projections, joined only by one
  non-authoritative comparator using the consistent `typed_mismatches` schema.
- Parent/progress vectors are synthetic resolver fixtures only and grant no source-adapter authority.
- The layout planner has no presentation input, cross-projection drift, mutation, or runtime role.
- Contract #4 exposes no mutation: its action allowlist is truthfully empty and fail-closed.
- Ten future paths were absent at review; collision, coherent sampling, revision, and reference-token
  rules are explicit.
- Unknown/freshness, privacy/redaction, low-cardinality telemetry, accessibility, consumer parity,
  review separation, and H1 `TBD` gates remain explicit.
- Frontmatter validation passed.

## Boundary

This PASS accepts only the exact hashes above as a `PREPARED_ONLY` design package. Any byte change,
contract-zero change, file-ceiling expansion, or authority expansion invalidates the verdict. Freeze
still requires the accepted H1 predecessor hash. Implementation and activation each require separate
owner authority and their own validation/review gates.

VERDICT: PASS — exact hash-bound PREPARED_ONLY H2A design package satisfies the declared acceptance criteria
