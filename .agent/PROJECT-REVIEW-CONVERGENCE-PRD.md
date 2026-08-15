---
doc_type: prd
id: review-convergence-soft-failure-20260815
title: Bounded Review Convergence
status: active
owner: codex-orchestrator
created: 2026-08-15
runtime_authority: false
---

# Bounded Review Convergence

## Problem and evidence

The HERDR H2A pure-projection slices reached repeated green implementer suites while independent review continued to reveal one new example in the same invariant family per pass. The findings were often real, but the workflow had no revision budget, no requirement to batch equivalence classes, and an unconditional `REQUEST_REVISION -> re-delegate` rule. This allowed serial counterexample discovery to consume review rounds and tokens without a convergence decision. The operator classifies this as a soft failure that must enter the self-improvement loop.

## Objective

Preserve independent, fail-closed review while preventing unbounded revision churn. Reviewers must assess and report the complete blocking equivalence classes they can establish in one pass. Repeated findings in the same invariant receive one repair replay; further recurrence escalates to the orchestrator for a contract-level decision. A total revision-pass budget mechanically prevents automatic re-delegation forever.

## Exact implementation slice

Modify only:

1. `scripts/ai/aq-loop`
2. `ai-stack/local-agents/loop_state.py`
3. `scripts/testing/test-aq-loop-review-repair-guard.py` (new)
4. `.agent/skills/reviewer-gate/SKILL.md`
5. `.agent/collaboration/RULES.md`
6. `config/doc-frontmatter-schema.yaml` (register typed implementation-review and escalated evidence state)

The PRD, issue ledger, resume, pulse, and handoff are workflow evidence outside this implementation ceiling.

## Contract

- `aq-loop` consumes a bounded structured review result instead of treating truncated prose as sufficient review state.
- Durable loop state records the exact review scope tuple, repair batch, invariant identifiers, finding hashes, and replay counters.
- All blocking findings from a pass are dispatched as one repair batch. A malformed, unknown, or `CONCERNS` result is non-accepting.
- One automatic replay is allowed per `(scope tuple, invariant_id)`. A repeated invariant becomes `ESCALATED`, creates one deduplicated issue/learning signal, and cannot trigger another automatic repair.
- Subject, baseline, criteria, roster, or policy drift requires explicit supersession; drift cannot reuse prior review credit.
- Reviewer instructions require blocker batching, stable acceptance criteria, invariant/equivalence-class labels, and blocking versus follow-up separation.
- The same invariant may be automatically repaired and re-reviewed once. A further recurrence produces `ESCALATION`, a learning-loop issue, and one orchestrator choice: narrow/clarify the frozen contract, split a follow-up, or reject the slice.
- New acceptance requirements introduced after freeze are non-blocking follow-ups unless they expose a correctness, security, data-loss, or authority defect in the frozen criteria.
- Safety is not waived: critical defects remain fail-closed and can reject the slice immediately.
- Reviewers must report all blockers found in the completed pass; serial withholding of already-discoverable blockers is prohibited.

## Acceptance

- New hermetic tests prove complete blocker batching, one replay per invariant, repeated-invariant escalation, scope-drift rejection, deduplicated escalation, and non-acceptance of malformed/unknown/`CONCERNS` results.
- Existing review-feedback and loop-state tests remain green.
- Skill and collaboration contracts use the same thresholds and escalation semantics.
- Python compilation, shell syntax validation, focused tests, scoped diff check, and staged-isolated Tier-0 pass before commit.

## Exclusions

No HERDR runtime, dashboard, adapter, control, service, deployment, rebuild, external call, or mutation authority. This slice does not weaken independent review or permit self-acceptance.

## Orchestrator convergence disposition

The production guard and real terminal-path tests are implementation-complete. Independent review confirmed the repaired terminal behavior but withheld PASS because the integration matrix does not separately replay a structured `UNKNOWN` verdict; that case is already rejected by the pure consumer test, while malformed and `CONCERNS` results traverse the real branch. The revision budget is exhausted, so this redundant composition proof is deferred as a non-blocking test follow-up. The commit must not claim independent acceptance or include a review trailer.
