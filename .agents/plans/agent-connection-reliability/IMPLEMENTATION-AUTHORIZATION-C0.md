# Prepared Implementation Authorization — Agent Connection Reliability C0

**Decision:** `implementation_authorized = true`
**Status:** `SUSPENDED — SONNET TRANSPORT FAILED WITHOUT CANDIDATE WRITES`
**Authorization ID:** `auth-agent-connection-reliability-c0-20260716`
**Idempotency key:** `acr-c0-f6b5acee-20260716-single-use`
**Prepared:** 2026-07-16 by Codex orchestrator
**Activated:** 2026-07-16 by explicit owner command
`Activate auth-agent-connection-reliability-c0-20260716`
**Suspended:** 2026-07-16 after task `claude-20260716-131724-n7266c` produced no candidate writes,
lost progress for more than three minutes, and required interruption/manual stale reconciliation
**Base commit:** `57b87e2d3235f9682592c8ddb9080f82794377eb`

## Reviewed design binding

- PRD SHA-256: `629ca89b714d691e305762366954070d492aa899d6c5e65a22102281f32ca17c`
- Program plan SHA-256: `07a1e9f3fd346da46838d060d0f308be3b6aeeaae46f547a73f66df1ba1d09e1`
- C0 packet SHA-256: `f6b5acee94e254ef2a9fab332a4f50bfe6a0322142e234a35e892f26c18ddccb`
- Antigravity flagship review SHA-256:
  `15993c2b25aa192d14638020771d88fd74aa9dea7c6a8a800ba3011d4517b4d5`
- Antigravity verdict: `PASS`
- Fable lane: temporarily unavailable; the owner reported capacity failure and directed Codex to
  proceed. This records unavailability, not approval or abstention.

Any drift in the PRD, plan, packet, or review before activation requires review refresh.

## Exact eleven-file grant after activation

| File | Authorized starting state |
|---|---|
| `.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md` | SHA `629ca89b714d691e305762366954070d492aa899d6c5e65a22102281f32ca17c` |
| `.agents/plans/agent-connection-reliability/PROGRAM-PLAN.md` | SHA `07a1e9f3fd346da46838d060d0f308be3b6aeeaae46f547a73f66df1ba1d09e1` |
| `config/schemas/agent-dispatch-envelope.schema.json` | absent; may create |
| `config/schemas/agent-dispatch-policy.schema.json` | absent; may create |
| `config/agent-dispatch-policy.json` | absent; may create |
| `scripts/ai/lib/agent_dispatch_contract.py` | absent; may create |
| `scripts/testing/fixtures/agent-dispatch-contract-golden.json` | absent; may create |
| `scripts/testing/test-agent-dispatch-contract.py` | absent; may create |
| `config/schemas/agent-ops-projection.schema.json` | SHA `4aace22c05cacc4bc1135b5c82976552dbb7e16d4f424d0a462240ddaa5d53e0` |
| `scripts/ai/lib/agent_ops_projection.py` | SHA `53491a1c27b7b270caea67a57dd5375c279242207668e8c98f96c9fa92ea3511` |
| `scripts/testing/test-agent-ops-projection.py` | SHA `241bee32bbc71f5513a2d4a17ba4434bffb7d6f0a80e65cc7bde01b0d9685fe9` |

The implementer may update PRD/plan status only to describe the exact C0 candidate and evidence. Any
twelfth implementation file is a hard stop and requires a new reviewed amendment.

## Implementer role and constraints

After explicit owner activation, one Sonnet implementer may create the pure contract-only candidate.
It must load `testing-patterns` and `strict-json-output-contract`, read the C0 packet and exact relevant
files, and remain within the eleven-file inventory.

The implementer must not:

- edit delegation wrappers, Nix, services, sockets, dashboards, live registry/PENDING/event data,
  provider configuration, credentials, network routes, or lifecycle stores;
- invoke Claude, Codex, local inference, Antigravity, systemd, providers, or network traffic;
- stage, commit, deploy, stash, pop, revert, archive, delete, or modify unrelated dirty work;
- claim runtime durability from pure fixture evidence;
- self-review or broaden C0 into C1.

## Required candidate evidence

1. Both schemas and policy are closed, bounded, Draft 2020-12 valid, and policy validates.
2. Focused tests cover every golden vector in the C0 packet with deterministic typed outcomes.
3. Duplicate/restart models prove at-most-once start under declared assumptions and fail closed on
   uncertainty.
4. Privacy canaries remain absent from lifecycle projection, metrics, and cards.
5. Existing `test-agent-ops-projection.py` and `test-local-delegation-reliability.py` pass.
6. Python compilation and JSON parsing/schema validation pass.
7. Exact candidate inventory and file hashes are recorded; no wrapper hash changes.
8. Tier0 passes on the exact staged candidate.
9. Independent flagship acceptance reviews the complete hashes before commit.

C1–C5, M2B, local reliability R1–R4, new stores, owner Q8, deployment, daemon/socket creation, live
traffic, and provider adoption remain unauthorized.

`RECORD: SUSPENDED without consumption. No C0 candidate exists. Replacement implementer authority requires Amendment 1 activation.`
