# PRD — Agent Connection Reliability and Durable Dispatch Fabric

Status: **C0 ACCEPTED AND COMMITTED (`4e3d96d3`) — C0.5 PLANNED; NO LIVE ADOPTION AUTHORITY**
Date: 2026-07-16
Owner intent: every local, remote, IDE, and future agent node uses one durable, observable,
fail-closed collaboration connection instead of fragile caller-owned background processes.

## 1. Evidence and problem statement

The current wrappers register a task and launch provider work with `nohup`/`disown` from the calling
agent. This is not a durable boundary. Managed agents commonly execute inside a sandbox, PID
namespace, cgroup, or process tree that is destroyed with its parent. Two correctly routed Fable
tasks returned live-looking PIDs, then died immediately with zero-byte logs when their launch command
returned. A user-systemd escape probe from the sandbox was denied by the user bus. Manual registry
reconciliation was required.

The same structural defect exists across Claude, Codex, local, Antigravity, retired Gemini, and any
future process-backed adapter. Additional failures compound it:

- generated `bash -c` supervisors reparse prompt/audit values and discard early stderr;
- five registry writers race and terminal status is frequently left `running`;
- PID visibility changes across namespaces and cannot prove host liveness alone;
- quota/session windows drop or wedge work instead of durably parking it;
- direct CLI, drop-zone, inbox, and local inference routes expose different lifecycle semantics;
- dashboards can show a registered task without a surviving executor.

This PRD consolidates Agent Ops M2B dispatch enforcement, RSI R8 parked delegation, the older dispatch
refactor, local delegation reliability, and wrapper parity behind one connection fabric. It does not
create another competing lifecycle authority: the accepted delegation registry remains the current
state spine until owner Q8 selects its successor.

## 2. Target architecture

```text
agent/client sandbox
  -> strict aq.dispatch.request.v1 over AF_UNIX
  -> systemd socket-activated aq-dispatchd (host execution boundary)
       -> admission/policy/budget/idempotency
       -> transactional TaskRegistry lifecycle writer
       -> provider adapter
          - local inference/switchboard
          - Claude CLI
          - Codex CLI
          - Antigravity inbox/collector
          - future declared adapters
       -> output/progress/heartbeat/terminal evidence
  <- strict ack/status/event envelopes
       -> Agent Ops TUI + web dashboard + aq-qa
```

Clients never spawn long-lived provider work. They submit one bounded request and receive a durable
task ID only after the daemon commits `queued`. The daemon already exists before sandboxed agents run,
so caller death, session eviction, terminal closure, or PID namespace teardown cannot kill accepted
work. Unix peer credentials identify the local caller; role/access/policy still require explicit
authorization and peer identity is not treated as hostile same-user authentication.

## 3. Canonical contracts

### 3.1 Request and acknowledgement

`aq.dispatch.request.v1` is closed, bounded, and versioned. It includes idempotency key, intended lane,
role/access class, task class, model tier/profile reference, execution mode, output expectation,
timeouts/budgets, review requirement, and a sealed prompt/input reference. Raw prompt content is not
stored in the registry, metrics, argv, journal, or default dashboard cards.

`aq.dispatch.ack.v1` returns task ID, record revision, admission state, adapter, contract version, and
typed reason. ACK means durable queued admission—not provider success. Duplicate idempotency keys
return the original task and never spawn twice.

### 3.2 Lifecycle

Canonical states are:

```text
submitted -> queued -> starting -> running -> waiting | parked
waiting -> running | parked
parked -> queued | cancelled | failed
running -> cancelling -> cancelled
queued|starting|running|waiting|parked -> done | failed | stale
```

Every mutation requires CAS revision and a daemon-owned fencing epoch. Exactly one adapter lease may
own a task. Terminal replay is idempotent; terminal-to-active is illegal. Daemon restart performs
evidence-based reconciliation and never blindly respawns an uncertain task.

### 3.3 Provider adapter contract

Adapters implement `preflight`, `start`, `observe`, `cancel_owned`, `classify_exit`, and `collect`.
They receive an argv vector or typed HTTP/inbox operation—never a shell string. They must provide a
host-visible execution identity or an explicit non-process lifecycle receipt. Each adapter declares:

- credentials and network boundary;
- concurrency and quota policy;
- prompt/input transport and redaction;
- heartbeat/progress evidence;
- cancellation authority;
- transient, quota-window, policy, auth, and permanent failure mapping;
- terminal and output completeness rules.

### 3.4 Error and retry taxonomy

Stable reason classes are `admission_denied`, `launch_failed`, `provider_transient`, `quota_parked`,
`auth_failed`, `policy_blocked`, `timeout`, `cancelled`, `output_incomplete`, `integrity_failed`, and
`executor_lost`. Raw provider errors are stored only in bounded protected evidence, not metric labels.

Short transient failures use bounded jittered retry. Long session/quota windows enter `parked` with
an earliest retry epoch and intended lane preserved. A scheduler resumes by idempotency key; it never
silently downgrades to another provider. Collaborative rounds remain open while a required lane is
parked and fold late evidence when it arrives.

## 4. Security and zero-trust boundary

- systemd owns `/run/aq-dispatchd.sock`; mode/group and `SO_PEERCRED` restrict clients;
- daemon runs without root, with explicit read/write paths, address families, executable allowlist,
  resource caps, and per-adapter network profiles;
- prompts enter through bounded stdin or sealed descriptor/file handling, never provider-visible
  command lines where supported;
- provider credentials exist only in the adapter service environment or `/run/secrets`;
- task IDs, paths, prompts, argv, model output, and raw errors are forbidden metric labels;
- cancellation can target only the daemon-owned process/cgroup/receipt for that task;
- malformed/unknown contracts and unavailable broker fail closed before provider work;
- same-user schema-valid forgery remains a residual threat until the future authority/state-spine
service separates writer credentials from agent credentials.

### 2.1 Model-tier and modality routing

Dispatch authority is independent of model price or vendor. Reasoning rounds use a flat expert-team
baseline. Once a slice is frozen, admission selects the cheapest healthy eligible implementer from
declared capabilities and current telemetry. Independent flagship reviewers accept or request a
bounded revision; only the orchestrator submits the accepted hash.

The local adapter exposes separate declared modalities for agentic coding/tools, bounded logic/direct
generation, and embedded retrieval. They share identity, policy, lifecycle, privacy, evidence, and
monitoring contracts, but have distinct hardware-aware context, phase-timeout, token, concurrency,
and tool budgets. Embedded retrieval cannot receive a role, execute tools, or cast a verdict. No lane
may bypass dispatch by calling a raw local or remote inference endpoint.

Zero trust means bounded capability and verified transitions, not loss of connectivity. Adapters may
retain full declared local or remote connectivity; no single agent receives general process, network,
registry, or credential authority.

## 5. Monitoring-first delivery contract

The fabric is incomplete unless all three service-coverage gates ship together:

1. `aq-qa` exercises socket admission, fake-provider execution, restart recovery, parking/resume,
   cancellation, and one real harmless canary per activated adapter.
2. Agent Ops TUI and web dashboard show broker/socket health, queue depth, starting/running/parked
   counts, adapter health, oldest queued/parked age, last terminal reason class, contract version,
   reconciliation count, and dropped/duplicate prevention.
3. Code, Nix service/socket, QA, and dashboard indicators commit in the same program slice or
   immediately consecutive activation commits.

Blank fields, stale running rows, zero-byte unexplained exits, or registered-without-executor states
are contract failures. Alerts are bounded and low-cardinality.

Review and feedback are operational state. Agent Ops and the dashboard expose each review pass and
baseline, required/received/parked/unavailable lanes, model tier and role lineage, subject hash,
verdict, revision/supersession, oldest wait, and feedback-promotion state. A delivered file without a
valid receipt is not a completed review.

## 6. Adapter-specific requirements

- **Claude:** explicit tier/model resolution; shared-quota reservation for flagship review; capture
  CLI exit before audit; no nested interactive-session assumptions.
- **Codex:** explicit sandbox/profile; no approval prompt in headless mode; correlate bwrap/cgroup
  without substring matching.
- **Local:** preserve strict inference schema, aq-chat parity, long generation budgets, progress and
  timeout phases, collision-safe IDs, and switchboard-only admission.
- **Antigravity:** inbox acceptance/archive is a first-class non-process adapter; headless collector
  and IDE work cannot be conflated; review tasks expose pending/processing/completed evidence.
- **Future nodes:** no adapter activation without the same contract, QA, dashboard, and security
  declaration.

`delegate-to-gemini` remains a fail-closed retirement surface and is not an adapter.

## 7. Success metrics

- 100% of accepted test dispatches survive caller termination.
- 0 provider starts before durable queued admission and executor attachment.
- 0 duplicate executions under retry, daemon restart, or duplicate submission.
- 100% of exits reach a typed terminal or parked state within the reconciliation SLO.
- 0 raw prompt/secret/argv/output values in registry, journal summary, cards, or metric labels.
- 100% adapter dashboard and `aq-qa` coverage before activation.
- no manual registry repair in the acceptance soak.
- 100% of critical reasoning/review passes record one baseline across participants and distinguish
  unavailable lanes from abstention.
- 100% of implementation candidates record economical eligibility evidence and receive independent
  flagship acceptance before submission.
- 100% of accepted findings link to an issue, regression/eval fixture, or explicit non-propagation
  reason; promoted corrections prove convergence and rollback across affected consumers.

## 8. Non-goals and stop conditions

No new database/event-log authority, owner-Q8 decision, arbitrary process kill, silent provider
fallback, prompt retention, web-dashboard redesign, inference protocol rewrite, external account
creation, or live cutover without a separate owner activation.

Stop for any adapter that requires caller-owned `nohup`, direct registry writes, shell-evaluated
commands, unbounded retry, untracked credentials, or monitoring exceptions.

## 9. Acceptance authority

Each slice needs exact inventory, hash-bound single-use authorization, implementor isolation,
independent flagship design/acceptance, focused tests, live evidence, Tier0, and explicit activation.
Failure or unavailable lanes are recorded, never converted into abstaining consensus.

### C0 evidence state

The Amendment-1 C0 candidate now provides the closed request/ack/status/event/adapter/failure
schemas, closed policy, pure CAS/fence/lease/idempotency model, adversarial golden fixtures, and a
pure Agent Ops contract-health projection. The projection deliberately reports the broker and all
adapter/service-coverage facts as `unavailable` until injected evidence exists; it does not claim a
live broker. C0 changes no route or runtime and remains pending independent flagship acceptance.
