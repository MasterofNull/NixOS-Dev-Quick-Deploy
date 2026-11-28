# ADR 0010: Local-only landing waiver

Status: Accepted (owner 2026-11-27)
Source: D-R5-1. Implementation slice: S2.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

During a Codex or Gemini outage the independent-review requirement blocks landing. An automatic fallback would let an author judge itself.

## Decision

A candidate-bound, owner-signed waiver stored out-of-band in the coordinator approval store, never in the candidate. Explicit mode `AQ_LAND_LOCAL_ONLY=1` plus the waiver. The record is stamped `assurance: local-only-waiver`, no review receipt is minted and it never satisfies a protected-branch rule. Any change to base, head, tree, policy revision or scope voids it. No automatic fallback.

## C1-C5 check

C1 PASS (local). C2 PASS. C3 PASS (in-repo). C4 PASS. C5 PASS (own work).

## Licence

In-repo.

## Reversal trigger

A waiver consumed without a matching signature, or a local-only landing treated as a receipt.
