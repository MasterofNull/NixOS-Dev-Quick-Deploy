# ADR 0012: lite profile budgets and the persistence/auth floor

Status: Accepted (owner 2026-11-27)
Source: D-R5-6. Implementation slice: S13.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

A 16 GB offline-capable install needs a defined budget and a safe floor for persistence and authentication.

## Decision

The budgets and floor are ratified as written in DESIGN.md section `lite` profile. The owner still names the 16 GB machine and the pinned model of at most 4 GiB (D14) before S13 measures anything. The owner approves any revision of the budgets.

## C1-C5 check

C1 PASS (local, offline). C2 must hold for `lite` (checked in S13). C3 pinned model and closure. C4 is this ADR's subject. C5 shipped model licence resolved.

## Licence

Model licence recorded per pinned model; unresolved fails.

## Reversal trigger

Budgets not met on the named real machine.
