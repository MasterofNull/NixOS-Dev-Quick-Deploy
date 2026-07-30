# L3-G0 Adoption-Boundary Independent Review

**Review date:** 2026-07-30
**Reviewer:** `codex-subagent-l3-l4-parity-gap-audit`
**Role:** independent architecture, contract, security, and SRE reviewer
**Subject:** `.agents/plans/local-inference-l3/L3-G0-ADOPTION-BOUNDARY-DESIGN.md`
**Subject SHA-256:** `ea47d4a274312f85790a556f744ed30a5af559e42f80086da60f96b616db52ee`
**Review scope:** design-only; no implementation or activation authority

## Independence and method

The reviewer did not author or edit the reviewed subject. The exact subject hash was
recomputed before review and matched the value above. Review compared the subject
against the local-inference contract PRD, the Foundation A adjudicated authority
projection, the current TaskRegistry/coordinator lifecycle boundaries, and the B1
chat/batch parity oracle and its field-level evidence.

This review created only this evidence record. It did not edit the subject, stage or
commit files, run a provider, modify runtime state, deploy, or activate traffic.

## Prior revision findings

The preceding review of subject SHA-256
`e06a3cae73576c07de9e94eba98b5bf7993a4a7b94c64e2d15881853e1a946ae`
returned `REQUEST_REVISION`. The revised subject closes all seven findings:

1. **TaskRegistry authority:** the host/coordinator dispatch broker is now the sole
   intended mutation boundary using TaskRegistry under its canonical lock/CAS
   contract. Coordinator lifecycle semantics are layered over that boundary rather
   than creating a second writer or store. Legacy/provider writers, reapers, inferred
   status views, and dashboard/file interpretations remain projections or
   compatibility evidence.
2. **Shadow identity:** L3-A observations use the distinct closed
   `aq.local-inference-shadow-observation/1.0` contract with `observation_id` and
   shadow-local ordering. The schema explicitly excludes live `run_id`, lifecycle
   sequence, event type, terminal/result, cancellation, retry, provider receipt, and
   writer-revision fields.
3. **Trusted ingress provenance:** every trusted fact class must bind a named producer
   and immutable revision. Headers, CLI flags, environment, PID/heartbeat state,
   provider output, task documents, and model text cannot become trusted sources.
   Missing, stale, ambiguous, or contradictory facts fail closed.
4. **Parity accounting:** the packet correctly preserves the B1 result as eight
   pair-level divergent statuses containing 24 field findings: eight
   `budgets.max_tokens`, eight `repeat_penalty`, and eight `repeat_last_n` findings.
   Both pair and field counts remain explicit acceptance obligations.
5. **Rollback semantics:** L3-A rollback only parks shadow observation while leaving
   live behavior untouched. A later L3-B rollback must preserve the canonical plan,
   authority decision, broker-owned lifecycle identity, and capability semantics; it
   cannot restore a legacy writer, direct provider route, caller-derived privilege,
   or divergent fallback.
6. **Chat telemetry ownership:** L3-A owns the shared shadow emitter and delegation
   producer while consuming existing chat evidence read-only. It cannot modify
   `aq-chat` or claim chat adoption; L4 exclusively owns chat producer/client
   migration.
7. **Successor sequencing:** L3-B is explicitly named as the separately designed,
   independently reviewed, hash-bound, and owner-activated live-adoption stage.
   L3-A shadow evidence cannot be represented as L3 completion or used to begin L4.

## Retained invariants

The revised design retains the required safety and operability boundaries:

- logical adjudication is not represented as physical convergence;
- `cycle1_authority` remains `NOT_AUTHORIZED`;
- L3-A cannot produce provider traffic, lifecycle mutation, a live terminal, retry,
  fallback execution, registry repair, or writer cutover;
- `direct`, `hybrid`, `agent`, and `ralph` are each translated or typed-denied with no
  implicit `default` fallback;
- exactly-one-terminal, idempotency, monotonic ordering, cancellation, and lifecycle
  identity remain future verified lifecycle-owner invariants, never shadow inferences;
- typed errors, schema repair, retry, and fallback cannot change role, tools, paths,
  scope, evidence, output schema, capability, or lifecycle authority;
- telemetry is allowlisted, bounded, redacted, low-cardinality, and separates
  interactive from batch latency and completion baselines;
- the Service Coverage gate requires live-backed dashboard state and an integration
  `aq-qa` check in the same release sequence as the L3-A contract implementation;
- all eight B1 pair statuses and all 24 field findings remain visible until resolved
  by live-shadow evidence; and
- the L3-A freeze must fail on overlap or drift involving L2B, L4, registry/CAS,
  storage, Nix, deployment, recovery, or any unlisted path.

## Scope and exclusions

This verdict approves the reviewed design for use in preparing a separately frozen
L3-A shadow-admission candidate. It does not authorize any code or test edit, process,
network/provider call, database connection or write, lifecycle or TaskRegistry
mutation, retry, runtime hook, service/Nix change, deployment, traffic, cutover,
legacy retirement, staging, commit, delegation, or activation. A later L3-A
implementation requires its own exact inventory, subject hashes, independent review,
authorization, and owner activation. L3-B and L4 remain separate future gates.

## Verdict

**VERDICT: PASS — exact subject
`ea47d4a274312f85790a556f744ed30a5af559e42f80086da60f96b616db52ee`
truthfully separates logical adjudication from physical convergence, closes all seven
prior review findings, preserves the broker/TaskRegistry and no-cutover invariants,
and is ready to govern preparation of a separately authorized L3-A shadow-admission
slice.**
