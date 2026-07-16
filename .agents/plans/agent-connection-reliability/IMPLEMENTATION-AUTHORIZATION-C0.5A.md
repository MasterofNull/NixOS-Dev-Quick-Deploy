# Conditional Implementation Authorization — Agent Connection Reliability C0.5A

**Authorization ID:** `auth-agent-connection-reliability-c0.5a-20260716`
**Owner authority:** owner preauthorized all bounded phases/slices/tasks on 2026-07-16
**Decision:** `implementation_authorized = true`
**Status:** `ACTIVE — AUTO-ACTIVATED AFTER EXACT ANTIGRAVITY DESIGN PASS`
**Idempotency key:** `acr-c05a-review-feedback-contract-20260716-single-use`
**Base commit:** `4e3d96d3`

## Activation predicate

This grant becomes `ACTIVE` without another owner prompt only when all are true:

1. Fable design review `claude-20260716-141123-n2apuq` remains `PASS`.
2. Antigravity returns `PASS` for exact design hash
   `c3136347a09c5e29ec88893015d2ed55df303b5eae46844fd13983eb6d485e00` and the five exact policy
   hashes recorded in `.agent/collaboration/antigravity-inbox/c05-design-review.md`.
3. No authorized file hash changes after that review.
4. The active implementer records the exact assignment before editing.

Any `REQUEST_REVISION`, mismatch, missing receipt, or changed hash keeps this authorization blocked.

## Implementer and routing

Route to the cheapest healthy eligible coding implementer for this multi-file strict-contract slice.
Current preferred lane is Claude balanced/Sonnet in monitored blocking mode because local exceeds its
measured multi-file/schema envelope and background caller-owned launch is not durable. The implementer
may not route other agents, self-review, stage, commit, stash, restore, deploy, or edit outside scope.
If the monitored lane loses progress or violates the output/scope contract, reconcile it and use a
fresh implementer amendment; never blind retry this key.

## Exact thirteen-file maximum implementation inventory

1. `docs/architecture/role-matrix.md`
2. `docs/architecture/local-agent-task-eligibility.md`
3. `.agent/PROJECT-LOCAL-AI-FACTORY-REFERENCE-ARCHITECTURE-PRD.md`
4. `.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md`
5. `.agents/plans/agent-connection-reliability/PROGRAM-PLAN.md`
6. `.agents/plans/agent-connection-reliability/C0.5-DESIGN-PACKET.md`
7. `scripts/ai/lib/review_feedback_contract.py` (new)
8. `config/schemas/review-round-receipt.schema.json` (new)
9. `config/schemas/learning-candidate.schema.json` (new)
10. `config/schemas/review-feedback-policy.schema.json` (new)
11. `config/review-feedback-policy.json` (new)
12. `scripts/testing/fixtures/review-feedback-contract-golden.json` (new)
13. `scripts/testing/test-review-feedback-contract.py` (new)

The six existing files are bound to the hashes in the pending Antigravity request. Files 7–13 must be
absent at assignment start. Any fourteenth implementation file is a hard stop.

## Required implementation outcomes

- One pure Pydantic/semantic SSOT with deterministic generated schema projections.
- No change/import that grants round persistence, lifecycle, registry, dispatch, provider, or consumer
  mutation authority.
- Total lane/verdict mapping; policy-driven quorum/terminal lattice; trusted independence and material
  rewriter recusal; critical advisory disposition; immutable independently verified learning evidence;
  CAS-gated promotion intent; closed local modalities and affected-consumer taxonomy.
- Every design-packet golden vector implemented with exact deterministic outcome.
- Existing round golden, aggregate, and decision suites remain green.
- Python/JSON validation and doc links pass before candidate handoff.

## Prohibited and deferred

No Agent Ops C0.5B files, live wrappers, collaboration CLIs, Nix, daemon, socket, dashboard, registry,
round data, prompt/skill/profile/tool/router/corpus/model/weight mutation, training, network, provider,
deployment, C1–C5 work, deletion, archive, or destructive Git action.

## Acceptance

Codex may validate and freeze the candidate but cannot accept its own implementation work. Exact
candidate hashes require independent Fable and Antigravity flagship acceptance before commit. A
reviewer that edits becomes a material rewriter and is recused from accepting the new hash.

## Activation record

Antigravity returned `PASS` on 2026-07-16 for design hash
`c3136347a09c5e29ec88893015d2ed55df303b5eae46844fd13983eb6d485e00` and the five exact policy
hashes. Receipt: `.agents/plans/agent-connection-reliability/antigravity-c0.5-design-review.md`.
Fable design PASS: `claude-20260716-141123-n2apuq`.

`RECORD: ACTIVE. Single-use C0.5A implementation may begin under the exact bounds above.`
