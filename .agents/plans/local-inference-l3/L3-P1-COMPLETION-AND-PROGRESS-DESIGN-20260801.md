# L3-P1 Local-Agent Completion and Progress Design

Status: `PREPARED_ONLY — DESIGN ONLY; NO RUNTIME CHANGE`  
Base HEAD: `99621ace21f1c60d7908ce82d8928f5001081592`

## Measured problem

The committed issue is: **“Local agent-mode: no COMPLETED signal + poor progress
visibility.”** Measurements show a cold start of approximately 394 seconds, an
average planning step of approximately 197 seconds, and eight steps taking about
26 minutes. Existing 420/1800/14400/4-hour budgets are adequate for this class
of work. The root defect is premature cancellation combined with no explicit
terminal `COMPLETED` linearization and hidden `steps.jsonl` progress—not a need
to simply increase timeouts.

L3-P1 is separate from L3-P0: P0 remains a pure provenance-shadow contract.
P1 must not adopt L3-P0, alter inference authority, or create live routing as an
incidental consequence of completion instrumentation.

## Grounded discovery inventory

The future implementation must re-read and re-pin at least:

| Existing seam | Current SHA-256 | Purpose |
|---|---|---|
| `scripts/ai/aq-agent-loop` | `e4fe98972fbddd21c7b5353fcba21d6bebf49fbdbde031302d94500e1e4c76db` | loop/wrapper invocation and cancellation surface |
| `ai-stack/local-agents/agent_executor.py` | `ad40178818172078c485d53fd10ef3a10afc7384ecf98b2dc6af7d2e25e44a98` | local agent lifecycle/execution seam |
| `scripts/ai/lib/dispatch.py` | `1b083b1025877385cb4e295234edd23a61a85aae554393fb87792c732e01dd92` | routing/admission boundary; no P1 authority widening |
| wrapper/status surfaces | re-pin before P1b | process status and `steps.jsonl` ownership/read seam |
| dashboard and API routes | re-pin before P1c | live projection only, not P1a/P1b shortcut |
| `scripts/testing/harness_qa/phases/phase0.py` and aq-qa registration | re-pin before P1c | Service Coverage gate |

No source is authorized by this design. It is an inventory, not an edit ceiling.
This parent is expressly **non-authorizable**: no owner may activate P1a, P1b, or
P1c until a separately reviewed slice packet enumerates every edit/new/no-edit
path and its exact current hash (or proves a NEW path absent).

## Phased smallest future ceilings

### P1a — pure terminal/progress contract

P1a is offline-only and creates a closed progress-event and terminal-result
contract, fixtures, and hermetic tests. Its event schema contains only task/run
opaque references, monotonic `step_index`, bounded step kind/state, and
`last_step_at`; counters for tools invoked and edits attempted/completed; a
typed progress classification; and a terminal sequence/result. It never stores
prompt text, tool arguments, tool output, paths from tool output, model text,
secrets, or raw error objects.

P1a freezes one terminal state machine:
`created -> queued -> running -> {completed|cancelled|failed|stalled}`; only the
braced terminal states are terminal and no transition leaves them. One designated
writer owns each `(run_id, attempt)` and persists append-only events with a
compare-and-swap expected sequence; temp-write, fsync, replace, and directory
fsync make the terminal transition atomic. Replay validates a stable PID/run
identity tuple `(run_id, attempt, pid_start_token)`, sequence, and event digest;
it returns the already-won terminal event, never re-runs work or emits a second
completion. A changed PID token, duplicate sequence, conflicting terminal,
truncated record, or partial write is typed unavailable/stalled and never
`COMPLETED`.

`COMPLETED` is emitted only after the worker has produced its final result and
all accepted progress events precede it. A duplicate, late, or conflicting
terminal event is typed and non-authoritative. P1a must prove deterministic
ordering, no terminal-before-last-progress race, crash/replay correctness, and
no false `COMPLETED` on cancellation, error, unknown worker state, or PID reuse.

The contract caps `step_index` at 10,000; tool/edit counters at 100,000; event
payload at 2 KiB; and retained events at 10,000 or 24 hours per run, whichever
comes first. Allowed step kinds are `planning|tool|edit|validation|finalizing`;
states are the frozen state-machine values; classifications are
`queued|slow_progressing|stalled|completed|cancelled|failed|unavailable`.
Times are UTC RFC3339 seconds from the designated monotonic-to-wall-clock mapper;
negative, future-skewed (>60s), or non-monotonic times fail closed. Metrics use
only low-cardinality labels `route`, `classification`, and `terminal_state`—no
run id, model, prompt, tool, path, or error text label.

### P1b — monitored runtime wiring

P1b may wire the P1a contract into the existing local agent executor and wrapper
only after separate review, exact source freeze, and owner activation. It writes
bounded `steps.jsonl` records atomically and exposes a read-only status seam.
Cancellation becomes progress-aware: slow work with advancing step index,
last-step time inside its bounded interval, or changing tool/edit counters is
`slow_progressing`, not stalled. `stalled` requires a configured no-progress
interval and no valid terminal state. Cancellation remains available and is
linearized as a typed terminal result, never silently rewritten as completion.

The runtime records a single-slot contention metric—queue/wait duration and
whether the only local slot is occupied—without task content or peer identity.
It must distinguish cold-start/queue wait from active slow planning. The default
budget for substantive local tasks is 30–40 minutes; a separate lighter route
is selected for trivial edits and must not consume the substantive route’s slot
or falsely inherit its success state. A trivial route may not claim separate
local capacity: it must be non-inference/deterministic, or it must be admitted
to the same one-slot queue and contention accounting as substantive local work.

### P1c — Service Coverage and bounded shadow dogfood

P1b runtime wiring, its integration AQ-QA check, and dashboard/API Service
Coverage are one release unit; P1c is only the bounded shadow-dogfood acceptance
phase after that unit is deployed. The release unit displays only progress state, step index,
last-step age, bounded tool/edit counters, terminal classification, contention,
and unavailable/error state. Blank or hard-coded fields fail acceptance. A
default-off, bounded shadow dogfood run must prove one slow-but-progressing task
is retained, one genuinely stalled task is typed, and terminal `COMPLETED` is
visible after successful completion. No provider traffic or production routing
is enabled by dashboard work. The shadow sample is exactly 10 deterministic
non-provider tasks, at concurrency 1, for no more than 40 minutes total; it may
not use a live provider, network, or production routing.

## Metrics, safety, and rollback

Acceptance measurements must include cold-start latency, planning-step latency,
completion rate, false-cancel rate, time-to-visible-progress, terminal
linearization conflicts, stalled-vs-slow classification accuracy, single-slot
contention time, and leakage-test count. The baseline is 394s cold start, ~197s
planning steps, and ~26m/8 steps. Success is fewer premature cancellations and
reliable visible completion without masking genuinely stalled work; it is not a
shorter timeout alone. The acceptance thresholds are: zero false cancellation,
zero false completion, zero prompt/tool-output leakage findings, 10/10 shadow
tasks with a visible terminal classification, and p95 time-to-visible-progress
no worse than the 394-second cold baseline plus 10%. Planning-step p95 may not
exceed the ~197-second baseline plus 15% without an explicit performance waiver.
Rollback is required if any zero threshold is nonzero, if p95 limits are exceeded,
or if the one-slot contention metric is absent/unavailable.

Every phase is default-off and independently reversible. Rollback disables the
new observer/wiring, retains bounded redacted evidence, marks uncertainty as
unavailable, and never fabricates `COMPLETED`. Any request to touch provider,
network, deployment, routing policy, L3-P0 candidate, or unlisted path is a
hard stop.

## Required review before execution

Each P1a/P1b/P1c slice needs its own exact inventory, hash-bound authorization,
distinct implementer and independent reviewer, and measurable acceptance record.
P1b/P1c additionally require Service Coverage review. This design grants no
implementation, staging, commit, runtime, provider, network, deployment, or
activation authority.

`RECORD: PREPARED_ONLY L3-P1 completion/progress design; P0 remains separate.`
