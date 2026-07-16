# C0 Design Packet — Agent Dispatch Contract and Failure Characterization

Status: **PREPARED_ONLY — FLAGSHIP REVIEW REQUIRED; NO IMPLEMENTATION AUTHORITY**
Parent: `.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md`
Base: `57b87e2d` plus uncommitted planning artifacts only
Date: 2026-07-16

## Objective

Freeze the pure, closed contracts and adversarial fixtures needed by the future host-side dispatch
broker. C0 changes no wrapper, daemon, Nix service, provider configuration, credential, registry data,
network route, or live traffic.

## Exact eleven-file maximum inventory

1. `.agent/PROJECT-AGENT-CONNECTION-RELIABILITY-PRD.md`
2. `.agents/plans/agent-connection-reliability/PROGRAM-PLAN.md`
3. `config/schemas/agent-dispatch-envelope.schema.json` (new)
4. `config/schemas/agent-dispatch-policy.schema.json` (new)
5. `config/agent-dispatch-policy.json` (new)
6. `scripts/ai/lib/agent_dispatch_contract.py` (new pure module)
7. `scripts/testing/fixtures/agent-dispatch-contract-golden.json` (new)
8. `scripts/testing/test-agent-dispatch-contract.py` (new)
9. `config/schemas/agent-ops-projection.schema.json`
10. `scripts/ai/lib/agent_ops_projection.py`
11. `scripts/testing/test-agent-ops-projection.py`

Any twelfth file or any import from a live wrapper/service is a stop condition.

## Contract requirements

- Draft 2020-12 closed schema for request, acknowledgement, status, event, adapter declaration, and
  typed failure evidence; every string, collection, integer, and nested object is bounded.
- Collision-resistant idempotency key, intended lane, role/access/task class, model tier/profile
  reference, execution mode, output expectation, timeout/budget, review requirement, and sealed input
  reference; no raw prompt, prompt-derived digest, argv, environment, headers, credentials, output,
  path, or provider error in lifecycle records.
- Pure state model with CAS revision, fencing epoch, one adapter lease, legal transitions, terminal
  idempotence, parked/resume semantics, and uncertain-restart failure closure.
- Closed reason taxonomy separating admission, launch, transient, quota, auth, policy, timeout,
  cancellation, incomplete output, integrity, and executor loss.
- Adapter declaration freezes preflight/start/observe/cancel-owned/classify-exit/collect capabilities,
  network/credential boundary, progress evidence, concurrency, and cancellation ownership.
- Pure Agent Ops projection exposes bounded broker/adapter/queue/park/terminal/contract-health fields
  without claiming a live broker exists.

## Golden failure vectors

Fixtures must include caller parent death, background PID disappearance, zero-byte exit, supervisor
stderr before task-log creation, shell metacharacters, duplicate idempotency keys, stale CAS, fence
loss, PID namespace mismatch, daemon restart with uncertain executor, short transient retry, long quota
parking, auth/policy hard failure, cancellation ownership mismatch, malicious oversized envelopes,
unknown fields, and privacy canaries.

The current `nohup` wrappers are characterization inputs only. Tests may read frozen source digests or
fixture snippets but may not invoke a provider, systemd, network, registry mutation, or live wrapper.

## Acceptance

1. Policy validates against its closed schema and unknown/undeclared configuration fails closed.
2. Golden vectors deterministically produce exact typed outcomes and legal next states.
3. Duplicate submission and restart models prove at-most-once provider start under the declared
   assumptions; uncertainty never becomes automatic respawn.
4. Privacy canaries are absent from projected lifecycle, metrics, and cards.
5. Contract health reports each required adapter capability and service-coverage gate distinctly.
6. Existing Agent Ops and local-delegation-reliability suites remain green.
7. Python compilation, JSON parsing/schema validation, and Tier0 pass on the exact staged inventory.
8. Independent flagship acceptance reviews exact hashes before commit.

## Explicit non-authority

C0 grants no daemon/client implementation, wrapper edit, systemd socket, AppArmor rule, live registry
writer, provider adapter, traffic, parked scheduler, lifecycle store, deployment, M2B activation,
local reliability R1–R4, or owner-Q8 decision.

`RECORD: C0 is PREPARED_ONLY. A reviewed, hash-bound, single-use owner activation is required.`
