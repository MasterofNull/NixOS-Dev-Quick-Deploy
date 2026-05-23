# Phase 58A.5 — Qwen Bounded-Task Eligibility Contract

## Objective

Define explicit, testable task-class eligibility for Qwen as implementer: which tasks it may complete autonomously (Tier A), which require a review gate (Tier B), and which it must escalate (Tier C). Provide complexity bounds, escalation protocol, and a promotion path.

## Outputs

- `docs/architecture/local-agent-task-eligibility.md` — eligibility contract
- `.qwen/SESSION-RULES.md` — eligibility SSOT pointer added
- `.agents/plans/phase-58a-qwen-eligibility.md` — this slice plan

## Acceptance criteria

1. Three task-class tiers defined (A: autonomous, B: review-gated, C: ineligible).
2. Complexity bounds stated per dimension (files, lines, timeout, context, tool calls).
3. Escalation protocol is concrete (stop → record → preserve → surface).
4. Promotion path defined with ≥3 clean PASS requirement.
5. Review gate integration references gemini-review-gate.md.
6. SESSION-RULES.md cites eligibility SSOT.

## Status

ACCEPTED — 2026-05-18 (Claude authored, Codex final acceptance complete)

### Evidence
- `docs/architecture/local-agent-task-eligibility.md` created with Tier A/B/C tables, complexity bounds table, escalation protocol, promotion path, hardware notes.
- `SESSION-RULES.md` Sub-Agent Boundaries pointer updated to include eligibility SSOT.
