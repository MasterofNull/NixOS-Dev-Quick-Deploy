# ADR 0009: aq-land-queue as the sole queue under the existing durable unit

Status: Accepted (owner 2026-11-27)
Source: D-R5-4. Implementation slice: S1b (after S2).
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

Landing used several overlapping queue scripts (`seqland*.sh`). The queue is the executor of the PR-branch-mutation decision and must not run twice.

## Decision

`aq-land-queue` is the only queue and is activated only after the S2 admission contract lands. It reconciles one exact response and holds on ambiguity; the seqland scripts are retired; bot-PR edits are preserved separately. A second queue start is refused.

## C1-C5 check

C1 n/a. C2 PASS. C3 PASS (in-repo). C4 PASS. C5 PASS (own work).

## Licence

In-repo.

## Reversal trigger

A crash, fencing or expiry case that the single queue cannot recover on real dependencies.
