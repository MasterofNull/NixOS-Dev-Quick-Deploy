---
title: "Local Inference L3-G0: Shadow Admission and Adoption Boundary"
slice: "L3-G0"
track: "AQ-OS local-inference contract / Foundation B"
status: "PREPARED_FOR_REVIEW"
kind: "design-only"
implementation_authorization: "NONE"
activation_authorization: "NONE"
base_head: "97131faac372e89273f14372edbfa5e52b816d64"
predecessors:
  - "Foundation A authority projection: 10/10 ADJUDICATED"
  - "L2B-B transport/payload adoption"
  - "B1 chat/batch offline shadow parity oracle"
successors:
  - "L3-A delegation-pipeline contract adoption"
  - "L3-B live adoption and scoped cutover"
  - "L4 aq-chat thin-client migration"
---

# L3-G0 — Shadow Admission and Adoption Boundary

## 1. Decision

L3 migration is permitted to prepare and exercise a **shadow-only local-inference
admission path** now that the Foundation A registry projects all ten authority targets
as `ADJUDICATED` and has zero owner-decision blockers.  That permission is deliberately
narrow: it admits only a read/projection-compatible request into a non-authoritative
contract path, produces bounded evidence, and leaves every current writer, provider,
and legacy CLI behavior live and unchanged.

It does **not** treat adjudication as physical convergence.  The same registry reports
ten observed physical-convergence blockers and `cycle1_authority: NOT_AUTHORIZED`.
Therefore live lifecycle-writer cutover, legacy writer retirement, durable-store
migration, database activity, routing cutover, and traffic activation remain prohibited
until separately measured convergence evidence and a separate owner activation exist.

This packet resolves the apparent circularity: L3 produces part of the convergence
evidence, so it cannot require completed convergence merely to begin its shadow
measurement.  It must, however, make no authority claim that would require the missing
convergence.

This is a design-only packet.  It authorizes no code edit, test edit, process,
database connection or write, service/Nix/deployment change, runtime traffic, staging,
commit, delegation, or activation.

## 2. Current truth and gate split

| Gate | Current evidence | Consequence |
|---|---|---|
| Logical authority decision | Foundation A projection: 10 `ADJUDICATED`, 0 `PENDING`, 0 owner-decision blockers | A shadow observer may bind its intended target boundary to the adjudicated lifecycle target. |
| Physical authority convergence | 10 observed convergence blockers; delegation lifecycle remains `SPLIT_BRAIN` | No writer may be replaced, retired, or represented as sole authority. |
| Cycle 1 authorization | Registry declares `NOT_AUTHORIZED` | No durable-store migration or new lifecycle store; no DDL, connection, or write. |
| B1 parity evidence | 4 byte-equivalent canonical projections and 8 typed divergences | The divergence list is a work obligation for L3/L4, not proof that adapters are ready for cutover. |

The adjudicated durable mutation target is one **host/coordinator dispatch-broker
boundary** using `TaskRegistry` under its canonical lock/CAS contract.  The broker is
the sole authoritative TaskRegistry mutator; provider wrappers, direct legacy writers,
reapers, PID/heartbeat inference, dashboard views, and file-status interpretations are
projections or compatibility evidence.  Coordinator run-lifecycle semantics—ordered
events, idempotency, cancellation, and exactly one terminal—are layered over that
broker-owned durable mutation boundary.  They are not a second writer/store and may
not bypass the TaskRegistry lock/CAS authority.

## 3. L3-G0 shadow-admission contract

### 3.1 Admission preconditions

A future L3-A implementation may admit an observation only when all of the following
are true:

1. The incoming request validates against the versioned local-inference request
   contract and is resolved by the shared pure resolver.
2. Every trusted ingress fact is an immutable value bound to a named producer and
   producer revision from the table below. Caller fields remain requests/information
   and may only reduce, never grant, capability.
3. The effective execution plan has a contract version, request/trace identity,
   selected profile/mode/model, budget, allowed tools/side effects, and fallback mode.
4. The request is explicitly marked `shadow`; the target coordinator contract path
   receives no authority to generate, invoke tools, mutate a lifecycle record, or
   affect a provider merely because it accepted the observation.
5. Any missing, ambiguous, malformed, expired, or contradictory trusted fact fails
   closed with a stable typed error and a redacted evidence reference.

The future L3-A freeze must pin the concrete producer identity and immutable revision
for every row; “current config,” mutable environment, or caller assertion is not a
revision:

| Trusted fact | Required producer + immutable revision source |
|---|---|
| authenticated caller identity and caller/model class | authenticated ingress identity mapper + signed/config-digest revision |
| effective role and clearance | shared pure resolver + role-policy revision |
| approval and descriptor lease | canonical lease issuer/verifier + signed lease ID, descriptor digest, and policy revision |
| profile and model mapping | canonical routing/profile registry + content/version digest |
| task eligibility and side-effect ceiling | eligibility-policy resolver + policy revision |
| token, timeout, queue, retry, and tool budgets | canonical budget resolver + policy/config revision |
| repository root, working directory, and permitted paths | trusted path resolver + repository identity/base revision and descriptor digest |
| time, expiry, and ordering inputs | broker-approved monotonic/wall-clock source + captured clock reading and clock-policy revision |

Headers, CLI flags, environment variables, PID/heartbeat state, provider output, raw
task documents, and model text are never trusted producers for these facts.  They may
be untrusted inputs or observations only.  An absent producer, absent/unknown revision,
digest mismatch, stale lease, noncanonical path, clock ambiguity, or contradictory
producer result returns a typed `trusted_fact_unavailable`/mapped public contract
error and emits no admissible shadow plan.

### 3.2 Shadow outcome

Shadow admission emits a distinct closed
`aq.local-inference-shadow-observation/1.0` record.  Its allowed top-level fields are:
`schema_id`, `observation_id`, `request_ref`, `trace_ref`, `shadow_sequence`,
`observed_at`, `producer`, `producer_revision`, `resolved_plan_digest`,
`legacy_observation_digest`, `compatibility_adapter`, `decision`,
`typed_error`, `divergence_findings`, `provenance_refs`, and the constant flags
`shadow=true`, `non_authoritative=true`, `no_live_cutover=true`.  Unknown fields are
rejected.  References are opaque/digested and provenance is redacted.

The shadow schema deliberately has **no** live `run_id`, lifecycle `sequence`, event
type, terminal status, result, cancellation token, retry instruction, provider receipt,
or writer revision. `shadow_sequence` orders observations only within its named shadow
producer; it conveys no lifecycle ordering or mutation authority.  It may compare the
resolved plan to a read-only legacy/chat observation when one is available, but that
input can never become a lifecycle fact.

The shadow path may not write a coordinator lifecycle store, update `TaskRegistry`,
rewrite a registry, publish a provider job, create a retry, select a fallback provider,
or use a shadow receipt as permission to transition a live task.

## 4. Lifecycle and TaskRegistry projection boundary

The eventual target has one coordinator-owned lifecycle with a monotonically ordered
event sequence and exactly one terminal event/result for each accepted run.  Terminal
statuses are `complete`, `partial`, `blocked`, `failed`, or `cancelled`; duplicate
idempotency keys attach to the same lifecycle and may not produce another terminal.

L3-G0 does not implement this target.  It fixes the adoption boundary for later work:

| Surface | L3-G0 / L3-A treatment | Explicitly prohibited |
|---|---|---|
| Host/coordinator dispatch broker | Intended sole mutation boundary; later live stages must mutate TaskRegistry only through its canonical lock/CAS API | Bypass mutation, parallel reconciler, or alternate durable lifecycle store |
| Coordinator lifecycle semantics | Layered contract over broker mutations; shadow may describe expected semantics only | Separate writer/store, live transition in L3-A, or terminal derived from observation |
| `TaskRegistry` | Durable target store mutated only by broker; read-only in L3-A shadow | Direct adapter/provider write, status repair, or lock/CAS change in L3-A |
| Legacy/provider writers and inferred views | Read-only compatibility projections with source identity retained | Rewrite, reconciliation, retirement, inferred authority, or implicit migration |
| `aq-chat` conversation state | Client UX/history projection only | Separate lifecycle state machine or terminal invention |

No component may synthesize a terminal result from a timeout, disconnect, stale PID,
missing progress, or a legacy file marker.  A terminal is valid only when emitted by
the lifecycle owner under the future verified contract.  Until that owner is live,
shadow observations remain observations, not terminals.

## 5. Compatibility adapter and ingress coverage

L3-A must use one explicit compatibility adapter for the current `delegate-to-local`
forms: `direct`, `hybrid`, `agent`, and `ralph`.  It preserves accepted legacy CLI
syntax only by translating it to the resolved contract request.  It must not restore a
legacy route, budget, role, tool grant, fallback, lifecycle transition, or direct
provider call when translation fails.

The adapter must record its version, legacy-mode classification, translated fields,
unrepresentable fields, and typed outcome through the redacted telemetry boundary.
It has an owner, removal deadline, and retirement gate.  Removal requires all of:

- measured compatibility use at or below the frozen removal threshold for the defined
  window;
- measured request/result parity and stable error-rate gates across every retained
  mode;
- no unresolved capability-changing fallback or unauthorized-side-effect evidence;
- a distinct owner activation approving retirement after physical convergence.

An explicit unsupported/unavailable profile, including Ralph, returns
`unavailable_profile`; it never falls through to `default`.  Unknown modes and
unrepresentable legacy flags return `invalid_request` or `ineligible` as applicable;
they never get a best-effort implicit route.

## 6. Typed errors, fallback, and repair

L3-A must use the contract's stable public errors:
`invalid_request`, `ineligible`, `unauthorized`, `unavailable_profile`,
`queue_timeout`, `inference_timeout`, `cancelled`, `transport_error`,
`malformed_result`, and `degraded_fallback`.  Messages are safe and bounded;
backend exception strings, raw prompts, commands, paths, secrets, and provider
responses are diagnostic-only and must not be exported as public error text.

Fallback is resolver-owned and explicit:

- `deny` blocks without changing capability;
- `queue` preserves requested capability within its budget;
- `same_capability` requires a versioned equivalence proof; and
- `best_effort` is opt-in only, sets `degraded_contract=true`, and enumerates the
  capability loss.

Neither compatibility translation, retry, schema repair, nor fallback may change
effective role, tools, paths, scope, evidence requirements, output schema, or
lifecycle authority.  A timeout is retryable only after evidence proves that no
terminal was produced.  Schema repair is bounded to one formatting repair and must
not expand context or authority.

## 7. Telemetry, privacy, and Service Coverage

A canonical shadow-observation emitter is implemented in L3-A together with the
delegation producer that calls it.  Existing chat evidence is consumed read-only for
comparison; L3-A must not modify `aq-chat`, inject a chat producer, or claim chat-side
adoption.  L4 exclusively owns `aq-chat` producer/client adoption into the same
observation and canonical request contracts.

The canonical emitter records delegation-produced observations and read-only chat
comparisons.
Before persistence it applies closed field allowlists, content-size bounds, command
and secret/PII redaction, and content digests.  Raw chat history, prompt text, tool
output, provider error bodies, absolute paths, and high-cardinality user identifiers
are not telemetry dimensions.

L3-A's required low-cardinality measurements are: admission count/outcome, contract
and result schema validity, source mode, selected lane/profile distribution,
compatibility-adapter use and unrepresentable flags, parity/divergence category,
fallback/degraded count, typed-error count, queue/TTFT/inference/total latency
buckets, evidence-reference validity, and unauthorized-side-effect count.  Baselines
must be measured separately for interactive and batch work so apparent parity cannot
hide an unusable chat regression.

The Service Coverage Contract applies before any L3-A slice is accepted: the same
release sequence must include an integration-level `aq-qa` check that exercises the
shadow/adoption boundary, a dashboard projection of its actual state and metrics, and
the service/contract implementation.  No hard-coded or `--` value is acceptance.
Dashboard labels must distinguish `current`, `target`, `shadow`, and `transition`.

## 8. Known parity gaps retained as L3/L4 obligations

The B1 offline oracle is successful evidence, not a cutover certificate.  It reports
**8 pair-level divergent statuses containing 24 field findings**: 8
`budgets.max_tokens` findings (chat fixed at 1024 versus the resolved delegation
budget), 8 `repeat_penalty` findings, and 8 `repeat_last_n` findings (set versus
unset).  Every later L3/L4 fixture and acceptance report must test and account for all
8 pair statuses and all 24 individual field findings; neither count may be collapsed
or inferred from the other.

| Obligation | L3 responsibility | L4 responsibility | Cutover condition |
|---|---|---|---|
| `max_tokens` (8 field findings) | Feed legacy delegation mode through the immutable resolved budget and report every pair mismatch | Remove chat-local fixed default in favor of the same resolved plan | 0/8 field findings across the affected live-shadow vectors |
| `repeat_penalty` (8 field findings) | Preserve/record adapter-originated sampling values without fabrication | Remove chat-local omission/default drift through canonical client | 0/8 field findings across the affected live-shadow vectors |
| `repeat_last_n` (8 field findings) | Preserve/record adapter-originated sampling values without fabrication | Remove chat-local omission/default drift through canonical client | 0/8 field findings across the affected live-shadow vectors |

No later report may collapse these into generic “parity passed,” omit the count, or
claim L4 duplicate-logic removal is safe until a new live-shadow matrix confirms
equivalent mode, profile, model, task type, role, tools, budgets, fallback, version,
stream content, and usage behavior.

## 9. L3-A expected inventory and overlap exclusions

L3-A must be a separately frozen, hash-bound implementation slice.  Its final
inventory is intentionally not authorized here; expected categories are limited to:

1. one shared ingress/client or compatibility-adapter seam for `delegate-to-local`;
2. the narrow batch/delegation adapter required to use it;
3. closed request/event/result/error schemas or pure resolver tests needed to prove
   the contract;
4. golden compatibility, lifecycle, error/fallback, and redaction vectors;
5. one canonical telemetry projection and its integration-level AQ-QA coverage; and
6. one dashboard projection required by Service Coverage.

The L3-A freeze must enumerate exact paths and SHA-256s after inspecting the then
current worktree.  It must exclude overlap with frozen or independently active work,
including `aq-chat` migration ownership (L4), L2B transport/payload files and frozen
dashboard/schema bytes, TaskRegistry/registry writer or lock/CAS work, coordinator
store/DB/DDL work, Nix/deployment/service changes, and any C0.3 recovery subject.
An overlap, drift, unlisted path, or need for a new authority is a fail-stop and
requires a new design/amendment rather than an expanded implementation.

## 10. Measured convergence, rollback, and activation gates

L3-A cannot retire a legacy adapter or cut over writer authority.  Its evidence must
instead establish baselines for: per-mode adapter use, request and result parity,
typed errors, duplicate/terminal anomalies, fallback capability deltas, cancellation
and restart observations, schema validity, unauthorized-side-effect count, telemetry
redaction coverage, and interactive/batch latency.

The mandatory next live stage is explicitly **L3-B — live adoption and scoped
cutover**.  L3-B must be separately designed, independently reviewed, hash-bound, and
owner-activated before L4 begins producer adoption.  Only L3-B may consider a limited
delegation-path cutover, and
only after independent review verifies: zero duplicate terminal events; one traced
lifecycle identity across queue, model, tools, and result; zero untelemetried tool
claims/unauthorized writes; explicit-profile typed failures; the frozen parity and
error-rate thresholds; and evidence that legacy writers have ceased for the scoped
traffic.  Physical convergence must be measured rather than inferred from a flag or
document.

L3-A shadow rollback means only: park new shadow observations, retain all observation
records/evidence, and leave the live path untouched.  It cannot “roll back” by changing
a writer or route because L3-A owns neither.  A later L3-B cutover rollback must
preserve the already-resolved canonical plan, authority decision, and broker-owned
lifecycle identity.  It may disable or reverse only the governed compatibility
adapter/cutover binding; it must never restore legacy lifecycle authority, a direct
legacy provider route, caller-derived privilege, or divergent fallback semantics.
A rollback cannot report success if terminal/result ambiguity remains; it preserves
that ambiguity as a typed, reconcilable finding.

## 11. Review and freeze criteria

An independent reviewer must verify all of the following against the frozen L3-A
candidate:

1. shadow admission cannot produce provider traffic, lifecycle writes, or a live
   terminal transition;
2. trusted ingress facts cannot be forged or elevated by caller fields;
3. every `direct`, `hybrid`, `agent`, and `ralph` input is explicitly translated or
   typed-denied without default fallback;
4. TaskRegistry mutation authority is broker-only under the canonical lock/CAS;
   legacy/provider writers and inferred views are projections, and L3-A introduced no
   mutation or reconciler;
5. exactly-one-terminal invariants are checked without fabricating absence evidence;
6. typed errors, fallback, retry, and repair preserve capability and authority;
7. telemetry is bounded/redacted and the dashboard/AQ-QA Service Coverage path is
   live-backed rather than cosmetic;
8. all 8 B1 pair-level divergent statuses and all 24 field findings (8 each for
   `max_tokens`, `repeat_penalty`, and `repeat_last_n`) are individually tested and
   remain represented as unmet L3/L4 obligations; and
9. the inventory has no overlap with L2B, L4, registry/CAS, storage, Nix, deployment,
   or recovery subjects.

The freeze packet must bind the base HEAD, design hash, exact candidate hashes,
authorization window, implementer and independent reviewer roles, validation commands,
measured baseline method, rollback evidence, explicit exclusions, and the statement
that neither review nor a passing shadow suite activates live traffic.

## 12. Non-goals

- No live lifecycle or provider writer cutover, legacy retirement, or new store.
- No database, DDL, Postgres, Redis, network/provider invocation, runtime hook, Nix,
  deployment, staging, commit, or traffic activation.
- No `aq-chat` thin-client migration or removal of its duplicated logic (L4 owns it).
- No L4 producer adoption before separately authorized L3-B live adoption/cutover.
- No relaxation of profile, role, tool, path, lease, fallback, or redaction policy.
- No invented terminal, telemetry, usage, latency, provenance, or convergence claim.

`RECORD: PREPARED_FOR_REVIEW. L3-G0 permits only design of a non-authoritative shadow admission boundary; physical convergence and live adoption remain separately evidenced and owner-activated.`
