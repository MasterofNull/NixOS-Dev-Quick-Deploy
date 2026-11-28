# ADR 0013: Upstream register and the attribution guard

Status: Accepted (owner 2026-11-27)
Source: D-R5-5. Implementation slice: S1c.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

Upstream extractions and removals had no lifecycle owner (`WORKAROUND-REGISTER.md` and an ignored `.upstream/`).

## Decision

`scripts/upstream/REGISTER.json` with owner-only transitions and a schema. A hook and the submit path refuse agent trailers in upstream-bound commits. An unregistered overlay fails tier0. Upstream contributions stay owner-authored: propose, do not push.

## C1-C5 check

C1 n/a. C2 PASS. C3 PASS (in-repo). C4 PASS. C5 PASS (own work).

## Licence

In-repo; upstream `ai_policy` stays unknown per target until read.

## Reversal trigger

Owner key provisioning for owner-only transitions is a prerequisite for activation.
