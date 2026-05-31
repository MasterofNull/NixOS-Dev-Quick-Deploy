# Phase 58 — Capability Expansion Foundation

## Objective

Create the shared foundation required before adding large new domain capabilities:

- one canonical role/routing contract,
- one capability lifecycle model,
- one domain activation design,
- one review-gated multi-agent execution policy,
- and one extensible shell / knowledge / QA pattern for future domains.

## Scope Lock

### In scope
- Canonical role matrix and routing reconciliation
- Gemini review-gate design
- Qwen bounded-task policy refresh
- Domain activation specification
- Capability registry schema
- Domain shell / AIDB namespace conventions
- Initial validation plan for future domain readiness

### Out of scope
- Full GIS, mobile, scientific, embedded, or security implementation
- Broad package installation into the default system closure
- Runtime behavior changes not needed to define the foundation
- Expanding Qwen into open-ended architecture or final acceptance work

## Workstreams

1. **Instruction-plane convergence**
   - Normalize role definitions for Codex, Claude, Gemini, Qwen
   - Identify generated vs hand-authored instruction surfaces
   - Remove stale model/port/profile drift

2. **Routing and review policy**
   - Define domain-tag extraction shape
   - Define local-task eligibility model
   - Define mandatory Gemini review artifact and enforcement path

3. **Capability lifecycle**
   - Define lifecycle states and transition evidence
   - Define runtime / operator / validation / rollback surfaces
   - Define registry fields for available, missing, candidate, promoted

4. **Domain foundation pattern**
   - Nix dev-shell template
   - AIDB namespace template
   - Per-domain smoke-test template
   - Domain activation payload template

## Planned Agent Split

| Agent | Planned responsibility |
|---|---|
| Codex | Orchestrate, synthesize, review, final acceptance |
| Claude | Architecture and risk review of the foundation design |
| Gemini | Research and proposal generation only; all outputs reviewed before use |
| Qwen local | Small bounded checks, inventories, or template validation only |

## Step Plan

1. Inventory all active agent/routing instruction surfaces.
2. Write canonical role and profile SSOT proposal.
3. Draft capability lifecycle and surface-contract schema.
4. Draft domain activation and capability-gap workflow contracts.
5. Specify review-gate behavior for Gemini and bounded-task rules for Qwen.
6. Review the foundation design against existing PRDs and workflow rules.
7. Validate with focused policy checks and `tier0` before any implementation slice commits.

## Validation

- Role model is consistent across every active agent surface.
- Profile inventory has one authoritative source and no stale budget drift.
- Gemini review gate has a concrete artifact and enforcement design.
- Qwen bounded-task policy is explicit and testable.
- Capability lifecycle states and required evidence are machine-readable.
- Future domains can be added without changing the base architecture.

## Rollback

- Keep foundation artifacts additive until accepted.
- Do not replace existing routing or instruction files in one shot.
- If a proposed SSOT conflicts with live runtime behavior, defer mutation and record the conflict before changing execution paths.

