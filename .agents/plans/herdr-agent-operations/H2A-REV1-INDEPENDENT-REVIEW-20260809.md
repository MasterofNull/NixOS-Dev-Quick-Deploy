---
doc_type: design-review
id: herdr-h2a-rev1-independent-review-20260809
title: HERDR H2A revision 1 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (independent aq_reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-09
---

# HERDR H2A revision 1 independent review

This record persists the independent, read-only review of the first five-document H2A
`PREPARED_ONLY` candidate. It grants no implementation, staging, commit, rebuild, HERDR runtime,
socket, pane, process, or activation authority.

## Exact reviewed subjects

| Subject | SHA-256 |
|---|---|
| `H2A-IMPLEMENTATION-INVENTORY-20260808.md` | `ffad7f9c4d3116736e990e200cc3ccfa001fd61f3b4239164f0aa73ade437a59` |
| Contract #2, operator context to layout planner | `c804193c554b7e6e1dd326a0bdc179ceee02dcbce06eca365ffc208eb7adf6f4` |
| Contract #3, operator context to web dashboard | `3444124572dd382238360f8b2bf9c87e8a2138aa2b8de6700c8a8cb205f5ed6c` |
| Contract #4, human controls to audited AQ actions | `f77d67c45d1c619cbea899196886526137f29b7ea18bdba5f3f25887e990824f` |
| Contract #5, HERDR observation to presentation health | `adefd0c6f19af27c306076f77da301fb0f2337e3cccc6fced18dad65fb3b98d3` |

All five subjects were untracked and unstaged at review time.

## Blocking findings

1. The declared contract-zero digest was stale. The live basis digest was
   `716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48`, while the candidate
   declared `12c9e58c593a987ac31f6f52f8170b0969355d179de3b4b0d5389528112d9b90` and did not bind the
   basis digest in its inventory.
2. The inventory assumed normalized adapters while excluding their implementation. Current sources
   did not provide several declared mission, hierarchy, gate, receipt, or safe-attention facts.
3. Typed drift had three possible derivation owners: operator context, presentation health, and the
   web envelope. One comparator contract and function had to own the join.
4. Contracts #2 through #4 listed field families but did not close required fields, nested objects,
   enums, bounds, or complete versioned envelopes tightly enough to provide a parity oracle.
5. Human-control safety was unproven. In particular, `aq-approve` lacked current-actor authorization
   and invoked side effects before the locked queue resolution/CAS, allowing concurrent duplicate
   effects. No control could be exposed until an exact authorized, fenced, idempotent handler matrix
   was accepted.
6. Collision evidence was absent: no EDIT preimage hashes, active-writer/lease results, coherent
   multi-source sampling rules, or reference collision/supersession behavior were bound.

## Preserved strengths

The reviewer confirmed truthful H1 `TBD` handling, no runtime/activation authority, bounded privacy
semantics, exclusion of sensitive/high-cardinality projection data, and strong unknown/accessibility
vectors. Frontmatter validation passed for the reviewed subjects.

## Disposition

The exact revision-1 candidate is rejected for freeze. A revised five-document candidate requires a
fresh independent review bound to its new hashes. Review activity performed no edits, staging,
commits, rebuilds, or runtime operations.

VERDICT: REQUEST_REVISION — restore or rebind contract-zero; inventory safe adapters and collision controls; freeze one drift join and exact schemas; prove exact audited, authorized, idempotent action paths
