# Local Active-Lease Grammar PRD

Status: IMPLEMENTATION
Date: 2026-08-28

## Problem

The prompt exposes a per-turn `_active_tools` lease, while the grammar builder
previously enumerated the broader registry. A registry-only enabled tool could
therefore be grammar-admitted despite being absent from the model-visible lease.

## Objective

Use only the exact per-turn model-format tool lease (`name` plus `parameters`)
to build cached GBNF. Normal calls, retries, empty-response retries, and
grammar repairs use that same lease. Requested grammar fails closed if the
lease is absent, empty, or malformed; disabled grammar and explicit prose-only
turns remain no-ops.

## Boundaries

- No tool, handler, authority, policy, deployment, or inference changes.
- No registry re-enumeration during grammar construction.
- A hot-swapped lease applies to the following turn only after its prompt is
  rebuilt.

## Validation

- Focused grammar and matcher suites, L3 P0, Python compilation, and diff check.
- Independent exact-subject review before integration.
