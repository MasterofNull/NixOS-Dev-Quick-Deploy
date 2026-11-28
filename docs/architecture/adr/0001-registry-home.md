# ADR 0001: Registry home: extend system-state-authorities.yaml (no second registry)

Status: Accepted (owner 2026-11-27, defaults answer)
Source: rev 4 D6. Implementation slice: S1.
Plan: `.agents/plans/control-plane-consolidation-20261122/DESIGN.md` (rev 5).

## Context

Ownership of decisions was stated in prose and in two registries that disagree. A second `decision-ownership.json` would add a parallel source of truth with its own drift.

## Decision

`config/system-state-authorities.yaml` stays the single ownership registry. S1 adds `contexts`, `decisions`, `endpoints`, `tools`, `scan_scope`, `boundary_exceptions` and `reference_exceptions` to it, with the schema in `config/schemas/system-state-authorities.schema.json`. No `decision-ownership.json`.

## C1-C5 check

C1 n/a. C2 PASS (YAML plus Rust, no Node). C3 PASS (in-repo, no new dependency). C4 PASS. C5 PASS (own work).

## Licence

In-repo; no third-party code.

## Reversal trigger

If the YAML cannot express a needed field without a second file, reopen with a measured example.
