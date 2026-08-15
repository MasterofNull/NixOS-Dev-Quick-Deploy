---
doc_type: design-review
id: herdr-h2a-rev5-independent-review-20260815
title: HERDR H2A revision 5 independent freeze review
status: complete
parent_prd: herdr-agent-operations
reviewer: "Gibbs (/root/herdr_h2a_independent_review; independent flagship reviewer)"
verdict: PASS
date: 2026-08-15
---

# HERDR H2A revision 5 independent freeze review

This is the binding read-only review of the H2A REV5 design and narrowly scoped
implementation-authority amendment. The reviewer authored none of the subjects and made no repository
modification.

## Exact reviewed subjects

| Subject | SHA-256 |
|---|---|
| `.agents/plans/herdr-agent-operations/H2A-IMPLEMENTATION-INVENTORY-20260808.md` | `a26ac20ce6e3dbf32ade485a0fa0a4835ffee3167ef39f4469d1cb101cd215d4` |
| Contract #2, operator context to HERDR layout planner | `8074632c4b73dbc37c4da98533a703c12af441ac37f3274e914232563de1ead5` |
| Contract #3, operator context to web dashboard | `f407bafeb12ad85a95a95a88406a5cf2e1a73d68622844aa104d23c9929ac9c7` |
| Contract #4, human controls to audited AQ actions | `b8cedf3b50e857bb5da028823dc94bc655deb4a4125f867498fc6778c3775f08` |
| Contract #5, HERDR observation to presentation health | `a000bac50fb663c4477227694a9632f5add52f0feb28565358062fad9e4f3cf8` |
| Contract zero, canonical AQ to operator context | `716525936cbeb12058e2351aad97a805f54019c31748082346449f754846be48` |

All six subjects were untracked and unstaged at review time.

## Accepted H1 prerequisite

H1 is correctly bound to atomic correction commit
`3f68911f87115973febed0dbccf2881da8c6fb51`, whose parent is physical implementation commit
`ea96bcbfc05fca32d164137fd2cef261f5c68acc`. The final independent H1 receipt is
`.agents/plans/herdr-agent-operations/H1-CORRECTION-INDEPENDENT-REVIEW-20260815.md`, SHA-256
`5b62525779871e57c7d842a9e55e80d6c5645f37e6ab32a787bb0569bc252ab0`, verdict `PASS`.

The correction commit contains exactly its declared eight-path manifest. Its five behavior/runbook
files retain the frozen hashes recorded by the inventory. The no-link package target and `herdr 0.7.5`
identity, real Home Manager evaluation PASS, deterministic SPDX SHA-256
`cfa9a5904c50fdc01ed839bd5f3f827dc6c57ec36e4191e61879900938da715c`, and staged-isolated
Tier-0 receipt are consistent.

## Scoped implementation authority

`implementation_authority: true` authorizes only these ten pure `NEW` paths:

1. `config/schemas/operator-context.schema.json`
2. `config/operator-context-source-to-field-ledger.v1.json`
3. `scripts/ai/lib/operator_context_projection.py`
4. `scripts/testing/fixtures/operator-context-golden.json`
5. `scripts/testing/test-operator-context-projection.py`
6. `config/schemas/herdr-presentation.schema.json`
7. `config/herdr-presentation-source-to-field-ledger.v1.json`
8. `scripts/ai/lib/herdr_presentation_projection.py`
9. `scripts/testing/fixtures/herdr-presentation-golden.json`
10. `scripts/testing/test-herdr-presentation-projection.py`

All ten were absent from the worktree, Git index, and history, with no target-specific active claim in
current collaboration intent/resume/delegation records. Both five-file ceilings are unchanged from REV4.
Any sixth file in either slice invalidates this authority.

## Authority boundary

- `runtime_authority` remains `false`.
- Contracts zero and #2–#5 retain `implementation_authority:false`; the inventory is the separate,
  narrowly bounded implementation authorization.
- No adapter, source reader, layout planner, observation collector, comparator, transport, API, TUI,
  web consumer, Phase-0 registration, dashboard, global ribbon, or control implementation is authorized.
- Contract #5 remains sole semantic owner of a future typed comparator, but no comparator implementation
  is authorized.
- Contract #4's human-control allowlist is empty. All controls remain `unavailable`.
- No HERDR binary, CLI, socket, process, pane, session, layout action, reconciliation, service, rebuild,
  deployment, or activation is authorized.
- Synthetic vectors prove resolver behavior only and cannot make unavailable source facts known.

The collision auditor's earlier wording that called the implementation flag false is superseded by the
exact reviewed inventory and its corrected audit. The current flag is true only for the ten pure paths.

## Verdict

The exact REV5 subjects satisfy the H1 prerequisite, collision, schema separation, comparator ownership,
empty-control, privacy, unknown-state, sampling, accessibility, consumer-parity, review-separation, and
authority-boundary criteria. Each completed pure slice still requires hermetic validation and its own
fresh independent hash-bound PASS before staging or commit. Runtime and integration remain gated.

The reviewer performed no edits, staging, commit, build, rebuild, deployment, activation, or HERDR
runtime action.

VERDICT: PASS — exact REV5 subjects freeze only the ten named pure NEW paths with runtime authority false.
