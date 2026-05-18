# Phase 58A.4 — Gemini Review-Gate Contract

## Objective

Define a concrete, enforceable review gate for Gemini's work: enforcement point, artifact form, verdict protocol, and categories that always require review. Upstream authority: role-matrix reviewer role definition.

## Outputs

- `docs/architecture/gemini-review-gate.md` — full contract
- `.agent/GEMINI.md` — review-gate pointer added to Step 5 discipline section
- `.agents/plans/phase-58a-gemini-review-gate.md` — this slice plan

## Acceptance criteria

1. Contract defines: trigger categories, enforcement point, required artifact form, verdict protocol (PASS/FAIL/REQUEST_REVISION), no-self-acceptance rule.
2. GEMINI.md references the contract document.
3. The contract cites role-matrix.md as upstream authority.
4. The `candidate → promoted` hook is noted for 58A.6 capability lifecycle.

## Status

COMPLETE — 2026-05-18 (Claude, pending Codex final acceptance)

### Evidence
- `docs/architecture/gemini-review-gate.md` created with 8 trigger categories, enforcement point diagram, artifact form requirements, verdict table, approval-mode policy, no-self-acceptance rule.
- `GEMINI.md` Step 5 updated with review-gate pointer.

## Notes

- Codex final acceptance deferred (rate-limited). The contract is complete and internally consistent with role-matrix.md.
- Gemini rate-limit policy (429 = transient, no config workaround) documented inline.
