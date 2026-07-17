# Implementation Authorization Amendment 2 — R0.1 Claude Completion

Authorization ID: `auth-agent-connection-reliability-r0.1-am2-20260717`
Idempotency key: `agent-connection-reliability:r0.1:claude-completion-am2:20260717`
Parent: `auth-agent-connection-reliability-r0.1-am1-20260717`
Status: **PREPARED_ONLY — PENDING INDEPENDENT FLAGSHIP REVIEW**
Issuer basis: the owner explicitly directed the orchestrator to retry the reopened Claude lane and
continues the standing preauthorization for bounded slices required to finish the reliability goals.

## Recovery basis

The AM1 Codex recovery implementer remained within the exact seven-file lease and stopped before a
completed candidate after its selected model reported capacity exhaustion. It produced no completion
claim, staging, commit, deployment, or self-acceptance. AM1 therefore remains unconsumed under its
interrupted-without-candidate rule. The Claude availability probe
`claude-20260717-100007-l40896` completed successfully through the monitored delegation wrapper using
the balanced tier resolved to `claude-sonnet-4-6`.

This amendment transfers only the unfinished completion lease to a new monitored Claude Sonnet task.
It does not accept the inherited code or reuse the orphaned 2026-07-16 Claude task.

## Frozen incomplete baseline

1. `scripts/ai/lib/task_registry.py`
   `e5d26404e2782347e84f3b60f1a1c9d8a1bdaf56cd80c53beb9e7fb47f4903cb`
2. `scripts/ai/aq-delegation-registry`
   `0e56ebcf10fe1d4a022b0f413e761a17ccf58b30278602c9f5c87cdcef6d39eb`
3. `scripts/ai/lib/agent_ops_projection.py`
   `3edf0cea2811176493fa0eb60885071c4064aa6442792f9e67e62a57878afcd3`
4. `config/schemas/agent-ops-projection.schema.json`
   `a58680b29eb3893e4446d113af8dee5c3a15d0aa69d623355de6252eb643a466`
5. `scripts/ai/aq-tui-dashboard`
   `8bab94bb7f7f1d2eb5757494be0bee2d5807a9a94e52578c3e7bd4790b10051f`
6. `scripts/testing/test-agent-ops-projection.py`
   `87c611a6748b6b7ad0a3a379e233e2355557264fd99482326e1cf889fa698786`
7. `scripts/testing/harness_qa/phases/phase0.py`
   `63a0ae47b83e92556b93c3660f940d2b117b7074c178869db5a9c56274460dd3`

Any pre-dispatch mismatch is a hard stop.

## Exact grant

One Claude Sonnet implementer may complete only the seven files above against:

- R0.1 design SHA-256
  `41079079cce71ce83e834a7e24a2373813fc3b8311d09d0e9c91a6f591c67633`;
- normalized partial audit SHA-256
  `d834e8c95eff63bab21f26707fa8b01b83d71ee7d4c0bb592d1497d4610271c1`;
- AM1 SHA-256
  `c44dbcc22cb45d9c8ba2e97ba321f4e3c1f8abc5a4757ddbd7d263db6615fad5`;
- AM1 authorization-review SHA-256
  `17e5571b56af65f8c92af688d08a4fccdf1c6f90d1644c4c2d3ab40a038bb97a`;
- the existing incomplete changes, including all scanner, CLI, projector, schema, TUI, 21-test-family,
  and Phase-0 work already present.

The remaining known work is limited to correcting the three test-contract failures reported before
the capacity stop, rerunning the full focused suite, and making only fixes proven necessary by those
results. The implementer must preserve projector purity, strict M2A mutation/show semantics, closed
reason vocabularies, bounded nonblocking source reads, monitoring projection, and all design bounds.

## Consumption and acceptance

The first Claude task to report a completed exact seven-file candidate consumes AM2 regardless of the
later review verdict. Provider failure or interruption without a completed candidate does not consume
it. A completed candidate receiving `REQUEST_REVISION` requires AM3; AM2 cannot be replayed.

The implementer may not stage, commit, deploy, delegate, or review its own work. Final integration
requires exact seven-file hashes, focused/adversarial results, Phase-0 and Tier-0 evidence, and an
independent exact-subject `PASS` from a different agent/session that did not author or materially
rewrite the candidate.

## Non-authority

No eighth implementation file is authorized. This amendment excludes registry data mutation or
migration, web-dashboard implementation, broker/service/wrapper changes, Nix or deployment changes,
live traffic, C0.6 implementation, C1–C5, prompts, memory, collaboration state, and rejected evidence.

`RECORD: prepared single-use Claude completion grant; inactive until independent flagship PASS.`
