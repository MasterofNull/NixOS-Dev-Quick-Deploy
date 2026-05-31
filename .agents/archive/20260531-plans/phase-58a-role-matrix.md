# Phase 58A.1 — Canonical Role Matrix SSOT

## Objective

Establish one authoritative role definition document that all agent instruction surfaces project from, eliminating the current ad hoc role text duplicated independently in each agent's instruction file.

## Inputs

- `docs/architecture/canonical-kernel-declaration.md` (upstream authority, 58A.0)
- `.claude/CLAUDE.md` — current Claude role text
- `.agent/GEMINI.md` — current Gemini role text
- `.qwen/SESSION-RULES.md` — Qwen constraints
- `AGENTS.md` — harness-wide agent policy
- `.agents/plans/phase-58a-capability-expansion-team-plan.md`

## Outputs

- `docs/architecture/role-matrix.md` — SSOT (created this slice)
- Updated projections: `.claude/CLAUDE.md`, `.agent/GEMINI.md` (role section replaced with pointer + summary)
- `.agents/plans/phase-58a-role-matrix.md` — this slice plan

## Scope lock

### In scope
- Role definitions derived from kernel responsibilities
- Role authority/constraint tables (may/must/may not/escalation)
- Model defaults (illustrative, not binding)
- Consequences for 58A.2–58A.5
- Projection updates (pointer + one-line summary in each instruction surface)

### Out of scope
- Instruction surface full rewrites (58A.3)
- Routing/profile inventory (58A.2)
- Qwen eligibility contract detail (58A.5)
- Gemini review-gate implementation (58A.4)

## Acceptance criteria

1. `docs/architecture/role-matrix.md` exists and cites the kernel declaration as upstream.
2. Every role has: may / must / may not / escalation trigger.
3. CLAUDE.md and GEMINI.md role sections point to the role matrix and carry only a summary projection.
4. No instruction surface defines a role authority that contradicts the role matrix.
5. The document states which open items remain for 58A.4 and 58A.5.

## Validation

- `grep -r "orchestrator\|implementer\|reviewer" docs/architecture/role-matrix.md` — all four roles present.
- Manual consistency check: each agent instruction surface's role summary does not relax any role-matrix constraint.
- Confirm no contradiction with the kernel declaration.

## Status

COMPLETE — 2026-05-18

### Evidence
- `docs/architecture/role-matrix.md` created with all four roles, model defaults, kernel-inherited constraints, and consequences for 58A.2–58A.5.
- `.claude/CLAUDE.md` Delegation section updated to pointer + summary projection.
- `.agent/GEMINI.md` Delegation section updated to pointer + summary projection.
- Open items §1 (sub-orchestrator delegation) and §2 (escalation time-bound) recorded in role matrix for 58A.3 follow-up.

## Rollback

Delete `docs/architecture/role-matrix.md` and revert the Delegation sections in CLAUDE.md and GEMINI.md to their prior text.
