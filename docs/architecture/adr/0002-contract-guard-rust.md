# ADR 0002: Contract guard: extend the Rust contract-validator; derived CONFIG_SCHEMA_REGISTRY

Status: Accepted (owner 2026-11-27)
Source: D-R5-3. Implementation slice: S1.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

Cross-context calls had no checked contract. The writer guards (Python) answer who writes state, not who calls across a boundary under which versioned contract. A second ownership list in `contracts/config` was a drift risk both Phase 0 reviewers raised.

## Decision

Extend `crates/contract-validator` (binary `harness-contracts`) with `contracts`, `boundaries` and `decisions --count`, driven from the registry in ADR 0001. `tier0.d/check-contracts.sh` runs always and fails closed. A required CI check `contracts-boundaries` runs the base-ref checker over the candidate as data; the candidate's own checker runs only in an unprivileged job on a trusted known-bad corpus. `CONFIG_SCHEMA_REGISTRY` is derived from the YAML `config_files` rows and tested 1:1. Python writer guards stay; they are ported to Rust only on a measured trigger.

## C1-C5 check

C1 n/a. C2 PASS (Rust, no Node). C3 PASS (`nix/pkgs/harness-contracts.nix`, no crate dependencies). C4 PASS (measured 2026-11-27: contracts 33 ms, whole-tree boundaries 905 ms, staged boundaries 93 ms). C5 PASS (own work).

## Licence

In-repo; the crate has no third-party dependencies, so there is nothing to clear.

## Reversal trigger

Port the writer guards only on a measured latency problem or a missed regression, with parity tests.
