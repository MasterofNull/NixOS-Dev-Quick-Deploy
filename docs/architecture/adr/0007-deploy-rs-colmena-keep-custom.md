# ADR 0007: deploy-rs and colmena: keep custom

Status: Accepted (owner 2026-11-27, defaults answer)
Source: rev 4 D4. Implementation slice: none.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

Both tools push NixOS configurations to remote hosts. This harness deploys one host through `aq-update`.

## Decision

KEEP-CUSTOM for the MVP. Revisit deploy-rs versus colmena only for a real remote-fleet requirement (U8). Re-run the fact sheets at S12.

## C1-C5 check

C1 n/a. C2 PASS. C3 PASS (deploy-rs 1.0.0; colmena nixpkgs 0.4.0, behind). C4 PASS (SSH push). C5 PASS as unmodified tools.

## Licence

deploy-rs MPL-2.0 and colmena MIT. Invoking an unmodified MPL binary is allowed (D12).

## Reversal trigger

A real remote-fleet requirement (U8).
