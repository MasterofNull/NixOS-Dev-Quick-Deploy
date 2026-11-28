# ADR 0011: Supported-install boundary, remote-lanes add-on and the C3 pin policy

Status: Accepted (owner 2026-11-27)
Source: D-R5-2. Implementation slice: S1d.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

C1-C5 cannot hold for the whole project: the Claude, Codex, Gemini CLIs and other Node programs are needed on the owner's host.

## Decision

The supported install is the `lite` profile and `ai-dev`, each with `roles.remoteLanes.enable = false`. C1-C5 are tested there only. The owner's host keeps the add-on ON and is exempt from the C2 closure test (D13). C3: every non-nixpkgs package in a supported closure is a `flake.lock` input or a fixed-output hash under `nix/pins/`; a bare `builtins.fetchTree` narHash or `lib.fakeHash` fails. An unresolved C3 or C5 entry is not PASS.

## C1-C5 check

This ADR defines the C1-C5 test scope; its own checks are `check-no-paid-api-required`, `check-no-node-closure`, `check-licence-closure` and the pin check (S1d).

## Licence

Per-dependency record of invoked, linked, vendored, modified or redistributed.

## Reversal trigger

A Node-pulling member of `ai-dev` found by the S1d scan: disable by default or move it to an add-on flag; never silently shrink the supported set.
