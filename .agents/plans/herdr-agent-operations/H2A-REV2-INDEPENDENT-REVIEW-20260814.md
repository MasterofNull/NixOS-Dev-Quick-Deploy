---
doc_type: design-review
id: herdr-h2a-rev2-independent-review-20260814
title: HERDR H2A revision 2 independent review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (independent aq_reviewer)"
verdict: REQUEST_REVISION
date: 2026-08-14
---

# HERDR H2A revision 2 independent review

This record persists the independent, read-only review of the revised five-document H2A
`PREPARED_ONLY` candidate. It grants no implementation, staging, commit, rebuild, HERDR runtime,
socket, pane, process, or activation authority.

## Exact reviewed subjects

| Subject | SHA-256 |
|---|---|
| `H2A-IMPLEMENTATION-INVENTORY-20260808.md` | `c18078e33309427a0913e9b10eb7de17b56e2edf234203acbc1b88b750413791` |
| Contract #2, operator context to layout planner | `3be844aef3f08b3efe8521ae865d68ed5a6d1c5f544ce81bad65a52c55e04b95` |
| Contract #3, operator context to web dashboard | `ad249a22e637882b6f8de8fca1c5e84d3bff077569088f9df15841321070c258` |
| Contract #4, human controls to audited AQ actions | `b8cedf3b50e857bb5da028823dc94bc655deb4a4125f867498fc6778c3775f08` |
| Contract #5, HERDR observation to presentation health | `224112ce0c8ac52e95b298b3b94a8147e29b966a6eb3f34b712a8b13d9a117ec` |
| Contract zero | `716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48` |

All subjects were untracked and unstaged at review time.

## Blocking findings

1. `aq.herdr.presentation.v1` had incompatible frozen schemas: the inventory used
   `projection_revision`, singular `source_digest`, and nested `expected`/`observed`; contracts #3
   and #5 used `observation_revision`, plural `source_digests`, and separate root groups.
2. `aq.herdr.comparison.v1` alternated between `mismatches` and `typed_mismatches`.
3. Mandatory parent/child, recent-progress, and `through_parent` vectors exceeded the permitted pure
   inputs, where those facts were explicitly unavailable or unknown.
4. Contract #2 required conflict/drift preservation but accepted only operator context and exposed no
   comparison field, so its closed output could not represent cross-projection drift.
5. Collision evidence said fifteen future paths while the two five-file ceilings contained ten.

## Confirmed resolutions from revision 1

The reviewer confirmed that contract zero was correctly hash-bound; unsupported future adapters were
unauthorized and failed closed; contract #5 was the sole intended comparator owner; contract #4's
empty action allowlist truthfully prevented unsafe controls; sampling and reference collision rules
were substantive; and privacy, accessibility, unknown semantics, H1 `TBD`, dynamic role assignment,
and no-runtime/no-activation boundaries were preserved.

## Disposition

The revision-2 candidate is rejected for freeze. The same five design documents may be revised only
to resolve the five findings above, then require another fresh hash-bound independent review.

VERDICT: REQUEST_REVISION — align presentation and comparator schemas, reconcile permitted envelopes with acceptance vectors, make layout drift representable, and correct the exact file count
