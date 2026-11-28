# ADR 0008: devenv: reference-only

Status: Proposed
Source: rev5 (was KEEP-CUSTOM in rev 4). Implementation slice: none.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

devenv 2.4.0 manages dev shells; `devenv machines` is experimental and overlaps `aq-update`.

## Decision

REFERENCE-ONLY. Revisit when `devenv machines` leaves experimental status.

## C1-C5 check

C1 n/a. C2 PASS for the tool (templates may pull Node). C3 PASS (nixpkgs 2.1.2, behind). C4 OK for dev shells. C5 PASS.

## Licence

Apache-2.0.

## Reversal trigger

`devenv machines` stable and a measured overlap with `aq-update` worth removing.
