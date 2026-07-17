# Implementation Authorization Amendment 1 — R0.1 Completion

Authorization ID: `auth-agent-connection-reliability-r0.1-am1-20260717`
Idempotency key: `agent-connection-reliability:r0.1:recovery-am1:20260717`
Parent: `auth-agent-connection-reliability-r0.1-20260716`
Status: **PREPARED_ONLY — PENDING INDEPENDENT AUTHORIZATION REVIEW**
Issuer basis: owner preauthorized all bounded phases/slices needed to complete the stated reliability
goals and explicitly directed continued progress with other agents/models when Fable or Claude is
unavailable.

## Why this amendment exists

The authorized Sonnet task `claude-20260716-175123-l8wp6u` exited on provider session limit before it
could finish the seven-file slice. It modified five leased files, did not modify the two leased test/
Phase-0 files, emitted no completion report, staged nothing, and did not self-accept. The parent key is
therefore not consumed by a completed candidate. Amendment 1 transfers only the unfinished bounded
implementation lease to a Codex sub-agent; the orchestrator remains reviewer/integrator and cannot
self-accept the implementer's work.

Parent authorization SHA-256:
`dad93e332419f075ea92081cc43a8269ee49b0570bf10f625ec360ec9e2e6442`.
The orphaned task's terminal registry state is `orphaned`; its 70-byte provider output has SHA-256
`afd14400b8d42c5d6471f5e18084ce3d6bf8d10c0a9fa57110d9e39267f6e598` and contains only the
session-limit message.

A Codex recovery sub-agent was mistakenly dispatched before this amendment completed independent
review. The orchestrator interrupted it immediately after it touched only the first two leased files.
It produced no completed candidate, staging, commit, deployment, or acceptance claim. The hashes below
freeze that post-interruption state so the recovery remains auditable.

## Frozen recovery baseline

The following current hashes are the incomplete inherited candidate, not accepted results:

1. `scripts/ai/lib/task_registry.py`
   `591a885a9f2b35ee0d9211c96adf4b2293c1aa60e3b013cc734d32301785b88f`
2. `scripts/ai/aq-delegation-registry`
   `0e56ebcf10fe1d4a022b0f413e761a17ccf58b30278602c9f5c87cdcef6d39eb`
3. `scripts/ai/lib/agent_ops_projection.py`
   `dbac6d1550a08afd639905b56516be84ab4f760f5692324c46aa1652e815d9cd`
4. `config/schemas/agent-ops-projection.schema.json`
   `59135083e7ad263ec2bd2deb9cb8e752b24847c4b30147b4d26245629963bb58`
5. `scripts/ai/aq-tui-dashboard`
   `fd1d437c57541c8ad91d1511e4dd23d86ed74f5d66a98e64f1d3e11be5bf7f69`
6. `scripts/testing/test-agent-ops-projection.py` (unchanged predecessor)
   `e721108f09c64bd8bcb3f502435e6d476c383fa9e6717371e3c663ad86f1fbbd`
7. `scripts/testing/harness_qa/phases/phase0.py` (unchanged predecessor)
   `97d43f92c7638a6be261ea1ba5934caa8a8e178370b58f48820c54dcde3dc5c4`

If any hash differs before the recovery implementer writes, stop and report concurrent drift.

## Grant

The assigned Codex sub-agent may inspect and complete only the exact seven files above against:

- R0.1 design SHA-256
  `41079079cce71ce83e834a7e24a2373813fc3b8311d09d0e9c91a6f591c67633`;
- independent design PASS in `R0.1-DESIGN-REVIEW.md`;
- the parent authorization's binding contract and non-authority clauses; and
- the independent partial-candidate audit in `R0.1-PARTIAL-CANDIDATE-AUDIT.md`, SHA-256
  `d834e8c95eff63bab21f26707fa8b01b83d71ee7d4c0bb592d1497d4610271c1`.

The implementer must preserve strict M2A mutation/show semantics, complete the missing adversarial
tests and Phase-0 coverage, keep the projector pure, and correct any partial-code defect proven by the
audit. Any eighth implementation file is a hard stop.

## Non-authority and acceptance

This amendment does not authorize the nine-file web visibility implementation, registry migration,
production registry mutation, deployment, traffic activation, C0.6, C1–C5, or edits to prompts,
memory, collaboration state, Nix, services, wrappers, rejected evidence, or authorization records.

The recovery implementer may not stage, commit, deploy, delegate, or review its own work. The first
replacement implementer to report a completed exact seven-file candidate consumes this implementation
grant, irrespective of the later review verdict. An interrupted attempt that produces no completed
candidate does not consume it. A final `REQUEST_REVISION` requires a new amendment and idempotency key;
this grant may not be replayed for repairs.

Completion requires exact seven-file hashes, focused/adversarial tests, Phase-0 and Tier-0 evidence,
then an exact-subject review by a distinct agent/session that did not author or materially rewrite the
final candidate. Only that independent final `PASS` authorizes orchestrator staging and integration;
it does not retroactively control whether the implementation grant was consumed.

`RECORD: single-use recovery grant; active only for the interrupted R0.1 seven-file foundation.`
