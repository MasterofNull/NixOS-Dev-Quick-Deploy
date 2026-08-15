---
doc_type: prd
id: terminal-review-dispositions-20260815
title: Terminal Review Dispositions and Forward-Only Remediation
status: active
owner: codex-orchestrator
created: 2026-08-15
runtime_authority: false
---

# Terminal Review Dispositions and Forward-Only Remediation

## Problem

Live instructions and executable consumers conflate implementation completion, review acceptance, commit, and activation. Several guidance files still direct `REQUEST_REVISION` back into the same slice. Coordinator paths can also derive acceptance from untyped substrings. This creates unbounded review churn, moving acceptance criteria, false completion, and unsafe acceptance/activation ambiguity.

## Canonical lifecycle

### Pre-implementation planning

Risk-appropriate planning has a bounded convergence sequence:

1. evidence-backed draft with explicit scope and acceptance criteria;
2. one parallel review round against the same draft, batching architecture, security, SRE, QA, and operability findings;
3. one synthesis/amendment;
4. one freeze review.

The freeze terminates as `PLAN_READY`, `PLAN_READY_WITH_FOLLOWUPS`, `PLAN_BLOCKED`, or `PLAN_REJECTED`. Noncritical unresolved disagreements become ADRs, declared assumptions, or later slices. Only missing authority, internally contradictory criteria, unsafe architecture, destructive/data-loss risk, or an unbounded activation contract blocks implementation. Low-risk work may collapse this to a concise plan plus freeze check.

Once frozen, acceptance criteria are stable. A post-freeze reviewer cannot add a retroactive blocking requirement unless it exposes a critical correctness, security, authorization, data-loss, or unsafe-activation defect in the frozen contract.

### Completed implementation

Review terminates the current slice. It never silently reopens or mutates it. The terminal states are:

- `ACCEPTED`: exact subject satisfies the frozen criteria.
- `IMPLEMENTED_FOLLOWUP_REQUIRED`: bounded implementation is safe to commit; review findings become a new explicitly scoped next slice.
- `ACTIVATION_BLOCKED`: implementation may be committed only when safe and inert at rest, but must not deploy, merge into an activating path, or expose controls until the next slice resolves the blocker.
- `REJECTED`: implementation is unsafe even while dormant, destructive, corrupting, authority-violating, or not cleanly isolatable; do not commit it.

Each non-accepted result binds the exact review scope and issues a next-slice descriptor where eligible. Review credit never carries across changed scope. Critical defects remain fail-closed; forward-only remediation is not permission to activate unsafe work.

## Ordered implementation program

1. Align live documentation and prompt guidance.
2. Extend the existing typed review-feedback contract with the four terminal dispositions, criticality/at-rest classification, activation state, and next-slice descriptor.
3. Replace coordinator substring/unauthenticated acceptance paths with strict typed receipt ingestion; make auto-merge advisory until commit authority exists.
4. Adapt `aq-loop`, collaboration rounds, and workflow-deviation intake to terminate the current slice and issue the next one.
5. Separate commit authority from activation authority in agent executor and PRSI paths.
6. Project disposition, next-slice, deviation, commit, and activation state into Agent Ops/dashboard and QA.

## Slice 1 exact documentation ceiling

Modify only:

1. `.agent/WORKFLOW-CANON.md`
2. `docs/architecture/gemini-review-gate.md`
3. `.agent/skills/reviewer-gate/SKILL.md`
4. `.agent/skills/slice-authoring/SKILL.md`
5. `.agent/skills/multi-agent-collab/SKILL.md`
6. `.agent/CODEX.md`
7. `.agent/collaboration/CODEX-REVIEW-QUEUE.md`
8. `scripts/ai/aq-loop` (comments/help text only; no runtime behavior in Slice 1)

## Slice 1 acceptance

- Every live same-slice auto-repair instruction is removed or explicitly limited to pre-freeze planning synthesis.
- All eight surfaces use the same four implementation dispositions and four planning dispositions.
- Guidance states exact rules for safe-at-rest commit versus blocked activation.
- `REQUEST_REVISION` is retained only as a reviewer input mapped to a terminal disposition and next-slice issuance, never unconditional same-slice re-delegation.
- Documentation/frontmatter checks, Python compilation for comment-only `aq-loop`, focused consistency search, scoped diff check, and staged-isolated Tier-0 pass.

## Exclusions

Slice 1 changes no runtime behavior. Later slices require separate claims, tests, independent review, and commits. No HERDR runtime, dashboard, service, deployment, rebuild, control, or activation authority is granted here.
