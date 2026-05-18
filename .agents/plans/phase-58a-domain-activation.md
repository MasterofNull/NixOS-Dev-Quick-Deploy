# Phase 58A.7 — Domain Activation Template

## Objective

Define a standard pattern for activating new capability domains so future expansion doesn't require bespoke orchestration each time. Any future phase adding a domain instantiates this template.

## Outputs

- `docs/architecture/domain-activation-template.md` — full template with domain tag schema, activation sequence, 6 required artifacts, rollback
- `.agents/plans/phase-58a-domain-activation.md` — this slice plan

## Acceptance criteria per team plan

1. Domain tag schema defined (kebab-case, ≤32 chars, unique). ✓
2. Instruction payload template included. ✓
3. Tool preferences section included. ✓
4. AIDB namespace binding included. ✓
5. Validation hook template included. ✓
6. Future domain can be described from this template rather than bespoke prose. ✓

## Status

COMPLETE — 2026-05-18 (Claude, pending Codex final acceptance)

### Evidence
- `docs/architecture/domain-activation-template.md` created with 6 required artifacts (PRD, lifecycle registry entry, instruction payload, validation hook, AIDB namespace, routing preference), domain tag schema, activation sequence (7 steps), rollback procedure, and example (safety-analysis domain).
