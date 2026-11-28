# ADR 0003: nh: bounded spike inside aq-update

Status: Accepted (owner 2026-11-27, defaults answer)
Source: rev 4 D2 (rev5 table). Implementation slice: S5.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

`aq-update` calls raw `nixos-rebuild` and `home-manager switch`. nh 4.5.1 wraps build, diff, dry-activate and GC, and fixes activation on systemd below 261 such as NixOS 26.05.

## Decision

ADAPT as a bounded spike: only the low-level build/diff/dry-activate/GC step INSIDE `aq-update`, behind a flag, in S5. The flag window is at most one full update cycle after the first live `aq-update --deploy` using it; then cut over (remove raw rebuild from `aq-update`) or delete the flag and the spike. Replace, never run both. Bumping the pin from 4.4.2 triggers the release-notes rule and an owner rebuild.

## C1-C5 check

C1 n/a. C2 PASS (Rust). C3 PASS (nixpkgs pin 4.4.2, behind upstream; reported as pin currency, not a C3 failure). C4 PASS (single binary). C5 PASS only as an unmodified invoked binary.

## Licence

EUPL-1.2. Invoking the unmodified nixpkgs binary is allowed (D12). Linking, vendoring or modifying is UNRESOLVED and needs an owner-signed waiver. The EUPL appendix compatibility with AGPL-3.0 is from licence text and not re-read at source.

## Reversal trigger

Sunset by the flag window above. The spike must preserve the pinned closure, scope, single privilege prompt and pre/post checks.
