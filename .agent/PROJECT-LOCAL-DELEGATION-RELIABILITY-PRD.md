# Local Delegation Reliability PRD

Status: **R0 ACCEPTED AND FROZEN — ANTIGRAVITY FLAGSHIP RATIFIED 2026-07-15**
Owner authorization: 2026-07-15, diagnose and fix local inference cutoffs and delegation failures
Relationship: prerequisite reliability program; it does not expand or modify the staged L2B-A authorization

## 1. Outcome

Make local inference slow-but-reliable: a healthy task may wait, prefill, generate, inspect novel
evidence, and use tools for as long as it continues to make measurable progress. The harness must
still stop duplicated loops, orphaned processes, wedged slots, unsafe concurrent writers, malformed
results, and explicit operator cancellations.

The system must never confuse token budget, wall-clock deadline, queue wait, prefill, generation
silence, exploration count, or process liveness. Each has separate evidence and a separate terminal
reason.

## 2. Evidence and confirmed defects

| ID | Confirmed defect | Evidence | Impact |
|---|---|---|---|
| D1 | Internal IDs use `aq-{int(time.time())}` | `scripts/ai/aq-agent-loop` | same-second launches share task/event/stream identity |
| D2 | Outer `TaskConfig.max_tokens` is not passed to the agent loop | `AgentRunner.run()` command | requested implementation budget is observational only |
| D3 | Executor imports static 256/800-token constants | `shared/llm_config.py`, `agent_executor.py` | tool JSON and final synthesis truncate; docs/runtime drift |
| D4 | First-token timer includes queue plus cold prefill | `_call_llama()` | a healthy queued request can fail at 420 seconds |
| D5 | Fixed self-watchdog defaults to 1,800–7,200 seconds | `aq-agent-loop` | progressing multi-turn tasks can be killed by elapsed time |
| D6 | Novel implementation exploration hard-aborts at 12 reads | `agent_executor.py` | useful repo discovery is mistaken for stagnation |
| D7 | Observation count hard-aborts independent of novelty | `agent_executor.py` | multi-source research is cut off despite progress |
| D8 | Cancellation records terminal state immediately after SIGTERM | `task_registry.py` | `cancelled` can coexist with a live writer |
| D9 | Direct `/slots` polling is a non-atomic admission check and local writers have no repository lease; routed inference is already serialized by the switchboard semaphore | parallel reproduction and switchboard source review 2026-07-15 | direct callers race admission and colliding tasks can share files; a second model-slot authority would create split brain |
| D10 | CLI/config/skill budget claims disagree | `llm-config` skill vs code | operators cannot predict effective limits |
| D11 | Monitoring has heartbeats but no queue/prefill/generation phase | delegation sidecars/dashboard | an alive wait is indistinguishable from a wedge |

The reproducing pair `local-20260715-080214-x8hlnq` and
`local-20260715-080214-f3c2vd` received one internal ID (`aq-1784127735`), exposed
`max_tokens:256`, produced no stream, and required repeated cancellation. Neither wrote files.

## 3. Governing invariants

1. **One identity:** the collision-safe outer run ID is propagated unchanged through wrapper,
   agent loop, events, progress, stream, tools, cancellation, and result.
2. **One budget decision:** one resolved budget object controls each call; code must not import a
   second static ceiling that silently overrides it.
3. **Progress extends work:** valid queue, prefill, token, tool, checkpoint, or novel-evidence
   progress renews its relevant lease. A generic heartbeat alone does not prove task progress.
4. **No infinite silence:** queue, prefill, generation, tool execution, and parent-orphan detection
   retain separate bounded silence policies with typed terminal reasons.
5. **Novelty over counts:** repeated identical operations may be stopped; novel reads and distinct
   evidence are context-budgeted and checkpointed, not killed by a small global count.
6. **Single admission authority:** the switchboard remains the sole local-model slot authority;
   direct `/slots` polling is never an admission grant. Writer authority is a separate atomic
   repository lease. Review/read-only work never gains write authority.
7. **Cancellation is observed:** terminal `cancelled` is recorded only after child and process group
   exit. Escalation from SIGTERM to SIGKILL is explicit and measured.
8. **Limits are visible:** every effective budget, phase timer, lease, renewal, and terminal reason is
   exposed through machine status and the dashboard.
9. **No fail-open fallback:** timeout or quota pressure cannot silently change provider, role,
   tools, side effects, or model capability.
10. **Existing safety remains:** strict UTF-8/JSON, context-size protection, malformed tool-call
    recovery, unbacked-write detection, reviewer separation, and security boundaries remain.
11. **Finite authority:** admission grants a non-self-renewable execution epoch and resource
    quantum. A worker or model cannot renew its own slot or writer authority. At exhaustion it must
    checkpoint, yield, and requeue through the scheduler.
12. **Linearizable ownership:** registry updates, lease acquisition, cancellation, and terminal
    publication use compare-and-swap or one serialized authority; stale owners cannot overwrite a
    newer generation.

## 4. Canonical runtime contract

Add a schema-validated policy SSOT, `config/local-delegation-runtime-policy.json`, containing:

- identity version and collision-safe format;
- admission classes and local-slot/write-lease concurrency;
- task-class budgets for tool-call, repair, and final-synthesis turns;
- queue, prefill, generation-silence, tool, cancellation-grace, orphan, and optional operator
  wall-clock policies;
- calibrated throughput/prefill inputs and safe headroom;
- duplicate-operation fingerprint thresholds;
- context checkpoint/compaction thresholds;
- compatibility aliases and deprecation dates for existing environment variables.

The schema closes every policy object. Environment variables may override only fields registered in
`config/env-contract.yaml`; machine status must expose source (`policy`, `profile`, `explicit`, or
`compatibility_alias`) for every effective value.

Admission policy must also define queue arbitration (FIFO or weighted FIFO), priority aging, maximum
continuous slot residency, execution-epoch and token/RSS quanta, bounded queue-age SLOs, checkpoint
requeue rules, and starvation detection. No worker/model-provided field can increase its priority,
epoch, lease duration, context ceiling, token ceiling, or RSS ceiling.

The switchboard scheduler owns model admission, queue order, and externally granted execution-epoch
renewal. The delegation dispatcher owns the repository writer lease using a descriptor-held kernel
lock rooted at the canonical Git common directory plus a monotonically fenced record updated under
a dedicated, never-replaced lockfile descriptor in the existing runtime root; this introduces no
lifecycle store. The stable lock spans record read, generation/version check, write-to-new-file,
file `fsync`, atomic replace, and parent-directory `fsync`. The replaceable registry/record inode is
never the serialization primitive. Generation CAS rejects an owner that opened the old inode before
replacement. Initial scope is the whole canonical repository/worktree, deliberately preferring
safety over path-level concurrency. Acquisition order is writer lease before the first model request;
the switchboard independently admits each request and releases its semaphore after that request. The
writer lease releases only after confirmed child death. A bounded metadata TTL is renewed only by the
dispatcher from trusted scheduler or observer evidence, never by the worker/model; TTL expiry
triggers cancellation but cannot steal a live descriptor lock. Stale recovery requires successful
stable-lock acquisition, prior PID-identity death proof, and a newer fencing token.

Every inference-capable request, including callers currently described as `direct`, must use the
switchboard admission path or fail closed. Direct llama health/metrics observation may remain, but it
cannot submit inference or treat `/slots` as authority. R1 must name and coordinate all required
switchboard and caller changes with L2B-B; it cannot silently create a bypass or absorb that work.

Existing environment names absent from `config/env-contract.yaml` are recorded as drift, not accepted
overrides. R0 cannot legitimize them. A later slice must register a canonical name or remove the live
alias in the same change that consumes the policy.

## 5. Liveness model

```text
ADMITTED -> QUEUED -> PREFILL -> GENERATING -> TOOL -> CHECKPOINT -> ... -> TERMINAL
               |         |           |          |
               +---------+-----------+----------+-- progress renews only that phase lease
```

- Queue progress: slot position/owner changes emitted by the authoritative scheduler. It must not
  consume the prefill lease. A generic heartbeat is liveness evidence only and renews no lease.
- Prefill progress: request accepted plus server/switchboard prefill evidence. Its deadline is
  derived from input tokens / calibrated prefill TPS + cold-cache headroom.
- Generation progress: valid decoded token/usage chunks. Deadline is silence since last valid
  progress, not total generation duration.
- Tool progress: allowlisted tool start/result, or an observer-authenticated tool heartbeat within
  an absolute per-tool cap.
- Exploration progress: a new `(tool, normalized arguments, result digest)` fingerprint or an
  explicit checkpoint/action. Duplicate fingerprints drive nudge then stop.
- Orphan progress: pidfd where supported, otherwise PID plus `/proc` start time, process-group ID,
  and session identity captured at spawn. Parent loss or identity mismatch reaps the child
  independently of inference progress.

Every renewable progress record is sequence-bound and contains the run ID, admission epoch, causal
operation ID, allowlisted producer identity, monotonic sequence/time, phase, normalized input
fingerprint, normalized result digest, and semantic-delta classification. Digests exclude volatile
timestamps, nonces, and transport IDs. Model-authored heartbeat/checkpoint claims are untrusted and
cannot renew authority. Sidecars are atomically replaced observer records; truncation, stale
sequences, producer mismatch, and tampering degrade health but never promote task status.

The switchboard assigns a per-request correlation ID and is authoritative for `QUEUED`; only
correlated server/switchboard acceptance may enter `PREFILL`, and only a correlated valid decoded
chunk may enter `GENERATING`. If per-request phase evidence is unavailable, the transition fails
closed as `phase_evidence_unavailable`; generic service health cannot substitute. Prefill calibration
records model/profile revision, measurement source, measurement time, cold/warm class, sample count,
uncertainty, applied headroom, and expiry. Stale calibration selects a conservative bounded policy
and emits degradation; it never creates an unlimited timer.

Writer leases are descriptor-bound to a canonical worktree and normalized path set, reject symlink
traversal and overlapping paths, carry an atomic fencing token, and bind owner plus run plus
admission epoch. They are acquired before inference, released only after confirmed process exit,
and recovered stale only after PID-identity and fence validation.

Cancellation is a linearizable, idempotent state machine:
`running -> cancelling -> cancelled|cancel_failed`, racing completion through one terminal CAS.
Exactly one terminal record may be published. Process death is confirmed before lease release or
`cancelled`; stale PID identity is never signalled.

Context and memory limits are immutable within an admission epoch. Pre-call admission accounts for
input plus reserved output tokens; checkpoint compaction preserves provenance and integrity hashes.
RSS breach or OOM produces a typed terminal reason, reaps the process group, releases authority only
after death, and records cleanup evidence.

Progress renews phase silence only; it does not create infinite capability. Every run has cumulative
externally granted bounds for generated tokens, model/tool calls, context/checkpoint bytes, epochs,
and total resource time. Exhaustion checkpoints and requeues or terminates with a typed reason.
Only an authenticated operator/scheduler policy decision may grant another capability epoch.

## 6. Delivery slices

### R0 — Contract and executable reproductions

Status: **COMPLETE / ACCEPTED / FROZEN.** Any byte change requires digest regeneration and fresh
independent acceptance.

Freeze the policy/schema, a live-source manifest, and executable characterizations for D1–D11:
identity collision, budget propagation, phase separation, exploration, fairness/starvation,
registry lost updates, fenced writer leases, PID reuse, cancellation/completion races, context/RSS
cleanup, and telemetry tampering. R0 uses only new fixture/contract files, imports no live path, and
makes no Phase-0, registry, dashboard, or runtime changes. An adoption guard proves the live path
does not yet import or consume the R0 module or policy and proves no inference-capable direct llama
bypass is considered compliant.

### R0M — Monitored-work prerequisite

Before any live R1 implementation, project every supported delegation/collaboration lane into one
traceable operations contract: stable task/run ID, role/model/profile, owning process identity or
explicit file-inbox state, phase, progress age, writer authority, terminal reason, and provenance.
The Agentic Ops surface must correlate and deduplicate wrapper/child processes and must distinguish
active work, idle daemons, completed/stale processes, local registry delegations, internal Codex
collaboration tasks, Claude wrapper tasks, and Antigravity inbox work. Raw command-substring matching
cannot be authoritative. R0M is separately reviewed and authorized; it may not adopt the R0 runtime
policy or change inference behavior.

### R1 — Identity, admission, and cancellation

Propagate the outer run ID; atomically serialize the local slot and writer lease; implement
fair queued admission, non-self-renewable epochs, fenced descriptor/path leases, registry CAS,
`cancelling -> cancelled|cancel_failed`, and PID-reuse-safe process-group exit confirmation.
R1 cannot start until R0M shows its implementation and review lanes live with task-level traceability.

### R2 — Budget and liveness integration

Pass the resolved budget into agent execution; retire static overriding constants; implement the
phase-specific progress leases and calibrated estimates. Fixed wall-clock remains opt-in only.

### R3 — Progress-based exploration

Replace global read/observation hard aborts with normalized duplicate fingerprints, checkpoint
nudge, context compaction, and bounded missing-resource repetition.

### R4 — Observability and promotion

Expose status/metrics/dashboard cards and Phase-0 checks. Run serial and contention fixtures plus
live cold/warm local tasks. Promote only when completion and cancellation SLOs pass.

Metrics are low-cardinality and keyed by bounded enums/profile classes, never run IDs or prompts:
phase duration/silence histograms, progress renewal/rejection counts, budget provenance, queue age,
slot/writer-lease contention, identity collisions, epoch yields/requeues, cancellation TERM/KILL/
failure, OOM cleanup, telemetry-integrity rejection, and typed terminal reasons.

## 7. Success metrics

- 10,000 generated run IDs and 100 concurrent allocator attempts: zero collisions.
- 100% equality of wrapper/run/event/progress/stream/result IDs.
- 100% of implementation tasks receive the policy-resolved call budgets; no hidden lower ceiling.
- Healthy token streams are never terminated for total elapsed time.
- Queue wait never consumes prefill or generation silence budgets.
- Novel-read fixture completes beyond the former 12-read limit; repeated identical-read fixture
  terminates with `stagnation_duplicate_evidence`.
- Cancellation: P95 terminal confirmation <=15 seconds; zero live process groups after terminal
  `cancelled`; forced-kill count visible.
- Concurrent local tasks serialize without identity collision; concurrent writers without a lease
  reject before inference.
- Every terminal cutoff has exactly one typed phase/reason and the effective policy evidence.
- Dashboard has no `--` for active phase, budget, progress age, queue owner, or terminal reason.
- Starvation fixture proves bounded queue age, priority aging, maximum residency, checkpoint/yield,
  and fair requeue; no worker can self-renew an epoch or quantum.
- 1,000 concurrent registry mutations lose zero updates; stale generations and fencing tokens are
  rejected deterministically.
- PID reuse, cancellation/completion races, and repeated cancellation publish exactly one terminal
  record, signal only the captured process identity, and release leases only after confirmed death.
- Context admission rejects overflow before a call; compaction retains integrity/provenance; RSS/OOM
  fixtures leave zero live process groups or held leases and expose typed cleanup metrics.
- Truncated, replayed, reordered, stale, forged-producer, and volatile-only progress records renew
  no authority and cannot promote a task state.

## 8. Non-goals and safety boundary

- No unlimited unobservable execution.
- No removal of context-window, malformed-output, repeated-missing-file, privilege, or side-effect
  controls.
- No new lifecycle authority/store, provider fallback, remote credential, live L2B cutover, Nix
  deployment, or autonomous commit permission in R0.
- No model identity is authority. Role, side effects, and file leases remain explicit contracts.

## 9. Exit gate

The PRD and implementation plan require independent flagship review. Each implementation slice is
performed by an implementer-tier model and independently accepted by a flagship reviewer. R1–R4
require fresh authorization after R0 evidence; R0M monitoring parity is a hard prerequisite to R1.
L2B-A resumes only after there are no active writers
and the reliability work cannot overwrite its exact staged inventory.
