---
doc_type: design-review
id: h2a-inventory-orchestrator-review-20260808
title: H2A inventory — independent orchestrator review
status: draft
parent_prd: herdr-agent-operations
reviewer: "Claude Opus 4.8 (independent; Codex is the H2A design owner)"
verdict: "CONCUR with REQUEST_REVISION — split per ratified contract-zero; freeze gated on accepted H1"
date: 2026-08-08
---

# H2A implementation-inventory — independent orchestrator review

Independent review of `H2A-IMPLEMENTATION-INVENTORY-20260808.md` (Codex is the design owner; its own
`H2A-INVENTORY-CODEX-REVIEW.md` is advisory self-review, not the independent gate — this is).

## Verdict: CONCUR with REQUEST_REVISION. PREPARED_ONLY; not freeze-ready.

The blocking issue is correct and load-bearing: the inventory still ceilings a single merged
`aq.herdr.projection.v1`, which contradicts the OWNER-RATIFIED contract-zero (compose
`aq.operator-context.v1` + separate `aq.herdr.presentation.v1`, `drift` as the join). Codex's own B1
identifies this. The inventory must split into two independently closed, independently digestible pure
projections before freeze:
- **H2A-P0** — `aq.operator-context.v1` only (schema + source-to-field ledger + pure resolver + golden
  vectors + privacy tests); NO HERDR import/binary/config/socket/process/pane/layout/package/runtime dep.
- **H2A-P0B** — `aq.herdr.presentation.v1` only; before a separately-authorized observation adapter
  exists, runtime/session/socket/layout fields are `not_authorized`/`unknown`/null — static H1 package/
  config facts must NOT be presented as observed runtime truth. Correct.

A combined API/TUI response later may use a closed transport envelope carrying BOTH complete schema
versions/revisions/digests — a transport view, never a third authority or merged projection. Agreed.

## Concurrence on retained strengths
The closed objects/enums, source-to-field ledger, bounded references/labels, replay/parity vectors, file
ceilings, and activation separation are sound and should be retained through the split. Codex B2–B7
(carried in the self-review) are accepted as the revision scope.

## Gates
- Revision: apply B1–B7, split into H2A-P0 + H2A-P0B matching ratified contract-zero → independent
  re-review → freeze.
- HARD predecessor: accepted H1 (its supply-chain report is still draft; commit/package proof pending).
  H2A cannot freeze/implement before H1 acceptance pins its frozen-input hash.
- No runtime activation. PREPARED_ONLY throughout.

RECORD: orchestrator concurrence; no implementation/runtime authorized.
