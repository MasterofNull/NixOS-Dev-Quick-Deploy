# Phase 58A.0 — Canonical Kernel Declaration

## Objective

Name the harness kernel explicitly before the team hardens downstream role, profile, and instruction surfaces. This prevents future cleanup work from projecting contracts from an architecture that still contains overlapping workflow, routing, and orchestration concepts.

## Inputs

- `docs/agent-guides/00-SYSTEM-OVERVIEW.md`
- `docs/architecture/front-door-routing.md`
- `docs/architecture/hybrid-coordinator-module-map.md`
- `.agents/plans/phase-58a-architecture-review-brief.md`
- `.agents/plans/phase-58a-capability-expansion-team-plan.md`
- `.agent/PROJECT-CAPABILITY-EXPANSION-MASTER-PRD.md`
- `.agent/PROJECT-CAPABILITY-EXPANSION-CODEX-PRD.md`

## Scope lock

### In scope
- Canonical kernel objects.
- Canonical vs adapter vs legacy component map.
- OS substrate vs harness application boundary.
- Forward rules for routing, workflow/session semantics, delegation/review, and memory writes.
- Consequences for later 58A role/profile/instruction slices.

### Out of scope
- Large coordinator refactors.
- Runtime behavior changes.
- Final retirement of legacy components.
- Capability-domain expansion itself.

## Step plan

1. Synthesize the current architecture review into one kernel declaration.
2. Define the minimum canonical object model:
   - request / task intent,
   - route / execution profile,
   - workflow / session,
   - delegation / review,
   - memory / evidence.
3. Classify active surfaces as canonical, adapter, legacy, or research-only.
4. State NixOS boundary rules and forward constraints.
5. Record what later 58A slices must inherit from this declaration.

## Acceptance criteria

1. There is one short architecture artifact that names the kernel without ambiguity.
2. Later role/profile/instruction work can cite that artifact as an upstream authority.
3. The document distinguishes current reality from target-state cleanup work.
4. It does not pretend existing legacy paths are already retired.

## Validation

- Manual consistency review against current architecture docs.
- Confirm no contradiction with the Phase 58A architecture review brief.
- Review before any runtime-affecting follow-up slice.

## Rollback

Delete the additive declaration artifact and revert later references if the team rejects the framing.
