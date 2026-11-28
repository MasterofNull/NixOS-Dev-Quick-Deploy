# ADR 0014: Retire in-repo pi-agent and continue-cli; opencode and models-dev go to the add-on via nixpkgs

Status: Accepted (owner 2026-11-27)
Source: D-R5-2. Implementation slice: S1d.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

`pi-agent`, `continue-cli`, `opencode` build with npm or bun (C2 FAIL); `pi-agent.nix` carries `lib.fakeHash` (a placeholder, not proof it was never built).

## Decision

Retire `nix/pkgs/{pi-agent,continue-cli}.nix`. `opencode` and `models-dev` consume nixpkgs and live in the remote-lanes add-on; `maigret` consumes nixpkgs. A local expression is retired only after a functional comparison, since nixpkgs availability does not prove equivalence.

## C1-C5 check

C1 PASS (local backends). C2 FAIL for the retired expressions, which is why they leave the supported install. C3 removes a `fakeHash`. C4 n/a. C5 n/a.

## Licence

nixpkgs licences for the replacements; resolved by `check-licence-closure`.

## Reversal trigger

A functional gap between the nixpkgs package and the retired expression.
