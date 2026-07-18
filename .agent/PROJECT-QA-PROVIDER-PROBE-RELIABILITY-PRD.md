# PRD — QA Provider Probe Reliability

Status: **PREPARED_ONLY / DESIGN_ONLY / REVISION 3 / NO IMPLEMENTATION AUTHORITY**  
Date: 2026-07-18  
Program owner: AQ-OS QA and agent-connection reliability  
Scope: reliable, bounded, observable health probes for process-backed agent-provider CLIs

Revision 2 resolves independent review `D0-DESIGN-REVIEW.md` SHA-256
`355d3017c18daa9bb6e5b82cb2240801bfc5be2013ee8b3fc46492f81d4c71af` R1-R4:
outer-signal cleanup, descriptor-bound group quiescence, implementable invocation/evidence plumbing,
split adoption/visibility inventories, and deterministic one-spawn machine normalization.

Revision 3 resolves sole remaining R5 from independent review SHA-256
`1ef328c095a90959f4764ae4e20f28e8373205209b2eff33ccacaf7850da0dd8`: the five-second
SLO ends at cleanup, disposition restoration, and one redelivery; only a restored default
terminating disposition guarantees signal termination and nonzero status. Custom/ignored behavior
is preserved and reported, not overridden by a forced exit.

## 1. Problem statement and evidence

Phase-0 check `0.6.1` currently invokes `scripts/testing/smoke-flagship-cli-surfaces.sh`
through `cmd_ok()`. These layers do not share one process-lifecycle or time-budget contract:

- `cmd_ok()` uses `subprocess.run(..., timeout=15)` and inherits the caller's stdin.
- The aggregate shell smoke permits **45 seconds per provider** and serially probes four
  providers (`codex`, `qwen`, `claude`, and `pi`), for a nominal provider budget of 180 seconds.
- The shell smoke wraps each provider in GNU `timeout --foreground`. The Python parent times out
  only the shell process. The foreground timeout intentionally does not establish an independent
  process group, so the two timeout owners cannot prove that descendants were resumed, terminated,
  killed, and reaped.
- A provider or descendant that reads the inherited terminal, forks, or stops itself can remain
  stopped or orphaned after the 15-second parent-only timeout. A normal nonzero provider exit can
  also be collapsed into the same boolean `False` as spawn failure or timeout.
- Callers that see only a resultless timeout may retry the entire aggregate, including providers
  that already returned a valid terminal failure. That duplicates expensive startup work and
  erases the first failure's provenance.
- Tier-0 currently allows 420 seconds for Phase 0, while the provider aggregate itself is killed
  at 15 seconds. Raising Tier-0 cannot repair the nested ownership defect.

This is a QA correctness issue: a probe can be reported failed while its process tree survives, or
retried after it already produced a valid failure. It is also an observability gap: the dashboard's
existing **QA Phase 0 Status** card shows totals and duration but not which provider is active, the
probe lifecycle state, or the typed terminal reason.

## 2. Goals

1. Give exactly one Python component ownership of each probe process session from spawn through
   terminal reap.
2. Detach probe stdin from the user's terminal and prevent probe lifecycle from depending on a TTY.
3. On deadline or interruption, execute `SIGCONT -> SIGTERM -> bounded grace -> SIGKILL -> reap`
   against the owned process group.
4. Preserve valid provider failures as final evidence; never retry a provider within one QA
   invocation.
5. Align per-provider, aggregate, Phase-0, Tier-0, and dashboard-safe budgets explicitly.
6. Emit a closed, low-cardinality failure class and bounded sanitized diagnostics.
7. Preserve the existing immutable QA evidence store as authority and add a bounded current
   active-provider heartbeat as a projection.
8. Add probe detail to the existing QA Phase 0 dashboard card; do not create a second QA panel.

## 3. Target design

### 3.1 One process-lifecycle owner

A small standard-library Python helper owns one argv-only process invocation. Its conceptual API is:

```python
run_owned_process(
    argv,
    *,
    cwd,
    env,
    deadline_s,
    term_grace_s,
    kill_reap_s,
    stdout_limit_bytes,
    stderr_limit_bytes,
    heartbeat,
) -> ProbeProcessResult
```

Required spawn controls:

- argv vector only; no shell, `bash -c`, or command interpolation;
- `stdin=subprocess.DEVNULL`;
- `start_new_session=True`, with the returned PID captured as the owned process-group identity;
- an explicit allowlisted executable resolved before spawn;
- bounded environment and declared working directory;
- stdout and stderr drained continuously so a full pipe cannot deadlock the child;
- retained stdout/stderr capped independently while excess bytes are drained and discarded;
- raw output never enters metric labels, the heartbeat, or default dashboard fields.

The helper preflights Linux `pidfd_open`, `waitid(...WNOWAIT)`, `/proc` identity, and subreaper
support, temporarily enables `PR_SET_CHILD_SUBREAPER`, and restores its prior value. Immediately
after spawn it opens the leader pidfd and records PID/PGID/SID/start time. Direct exit is observed
without reaping: the zombie leader anchors the PGID until the final group decision, preventing
reuse. Before **every** return, including leader exit 0, the helper enumerates non-zombie members
with the recorded PGID/SID, descriptor-binds them where possible, and requires two consecutive
quiescent observations. A zero-exit leader with a live descendant enters cleanup and returns
`cleanup_failed`. Adopted owned descendants are reaped; unrelated children are never waited.

On deadline, interruption, or residual membership it executes `SIGCONT -> SIGTERM -> grace ->
SIGKILL -> quiescence -> owned-descendant reap -> leader reap`. Numeric group signals are allowed
only while the matching leader remains unreaped and its pidfd/start-time/PGID/SID identity is valid;
after leader reap they are forbidden. `ESRCH` requires descriptor/enumeration confirmation and is
never proof alone. A pidfd-open failure terminates and reaps the demonstrably live direct child and
returns `contract_invalid` without a later numeric group signal.
No kill by stale numeric PGID is permitted under any return or cleanup branch.

### 3.1.1 Outer SIGTERM/SIGINT contract

The main thread uses `signal.pthread_sigmask(SIG_BLOCK, ...)` to block SIGTERM/SIGINT while saving prior dispositions, installing minimal handlers
and a nonblocking wakeup pipe, and committing ownership, then restores the prior mask. Handlers only
record the first signal, coalesce later signals, and wake the selector. A second signal cannot bypass
cleanup or reset grace. The selector enters the same idempotent cleanup path as deadline expiry.

The controller remains installed through cleanup and one immutable-evidence publication attempt.
Cleanup is bounded to **4 seconds** from first signal (2-second TERM grace, 1-second KILL reap, and
1 second for identity/quiescence). Publication may consume only the remainder of a **5-second
cleanup/restoration/redelivery SLO** through a bounded worker. Then the main thread restores the
exact prior handlers/mask, closes wakeup descriptors, and re-delivers the first signal exactly once.
The SLO ends when that redelivery occurs.

If the restored disposition is the default terminating disposition, the production path must
terminate by that signal and cannot yield PASS or exit 0. If it is `SIG_IGN` or an arbitrary custom
handler, the ignored/handler behavior after redelivery—including return, explicit exit 0, blocking,
or later termination—is outside the lifecycle helper's control and outside the five-second SLO.
The helper does not force an exit after custom/ignored behavior. Evidence reports the prior
disposition class (`default_terminating|ignored|custom`) and whether redelivery occurred, separately
from child cleanup result. Tests send real outer SIGTERM/SIGINT and distinguish default termination,
returning custom handler, non-returning custom handler, and ignored disposition; internal
cancellation is insufficient.

Python cannot reap a daemon that deliberately escapes into a new session. The test contract must
prove ordinary fork descendants are contained; a provider that daemonizes/escapes is a policy
violation reported as `cleanup_failed`, and future cgroup ownership belongs to the dispatch broker,
not this QA helper.

### 3.2 Closed result and failure contract

`qa.provider-probe-result.v1` is closed (`additionalProperties: false`). Success uses
`result="pass"` and `failure_class="none"`. The complete failure enum is:

```text
none
executable_missing
spawn_failed
exit_nonzero
provider_reported_failure
machine_output_missing
machine_output_invalid
deadline_exceeded
output_limit_exceeded
cleanup_failed
interrupted
probe_busy
contract_invalid
```

The record includes only schema version, invocation ID, provider ID from a closed allowlist, argv
profile ID (not raw argv), lifecycle state, monotonic start/end/duration, deadline, exit code when
known, failure class, termination actions, truncation flags, sanitized stderr summary, and evidence
digest. It excludes prompts, credentials, HOME contents, raw environment, terminal data, arbitrary
paths, and full provider output.

Sanitized stderr is UTF-8 replacement-decoded, control characters removed except newline/tab,
credential-shaped values redacted, path prefixes reduced to declared tokens, capped at **4096
bytes**, and never used as a metric label. Retained stdout is capped at **65,536 bytes** for protocol
validation but is not stored in the heartbeat or dashboard. If either stream crosses its cap, the
helper continues draining, sets the matching truncation flag, and returns
`output_limit_exceeded`; a truncated result cannot pass.

### 3.3 Machine normalization and attempt policy

Profiles declare `exit_only` or `machine_json_v1`; current help profiles may remain `exit_only`.
Machine JSON is one closed object with schema version, `status=pass|fail`, and bounded reason code.
Lifecycle failures win; truncated output is `output_limit_exceeded`; empty output is
`machine_output_missing`; malformed/multiple/schema-invalid output is `machine_output_invalid`;
valid reported failure at exit 0 or nonzero is `provider_reported_failure` with exit code retained;
reported pass plus nonzero is `exit_nonzero`; reported pass plus zero is PASS/`none`. Every golden
vector asserts `spawn_count=1`; normalization never retries.

### 3.4 Budgets

The fixed initial budget table is:

| Boundary | Budget | Contract |
|---|---:|---|
| One provider startup/help probe | 45 s | One attempt only. |
| SIGTERM grace | 2 s | Per timed-out/interrupted provider. |
| SIGKILL reap | 1 s | Per timed-out/interrupted provider. |
| Four-provider sequential aggregate | 200 s | 4 x (45 + 2 + 1) plus 8 s orchestration margin. |
| Phase-0 host invocation | 210 s minimum for this check | Must not wrap the provider runner with a shorter deadline. |
| Tier-0 Phase-0 outer gate | 420 s | Existing ceiling; remains greater than the host aggregate. |
| Dashboard-confined Phase 0 | No live provider execution | Existing host-only skip remains; it reads the heartbeat/evidence projection. |

Each provider is attempted at most once per invocation. `exit_nonzero`, including a valid provider
diagnostic exit, is terminal evidence and is not retried. Timeout and spawn failures are also not
retried by this QA check. A later invocation may probe again under a new invocation ID; it cannot
overwrite or relabel prior evidence.

### 3.5 Evidence and active-provider heartbeat

The immutable QA store remains sole authority. `main.py` reserves its `Invocation` before creating
`RunContext`; exact run ID, sequence, and start time flow through context to Phase 0 and the runner.
Standalone compatibility execution does not write the canonical heartbeat or invent an invocation.
`CheckResult` gains optional schema-tagged typed `details`; provider detail validates as
`qa.provider-probe-result.v1`. `CheckResult.to_dict()`, JSON reporting, and immutable publication use
one serializer preserving structured details. JSON hidden in description/reason is forbidden. The
interrupted path carries partial checks and typed failure to `main.py` for the one bounded publish
attempt before signal re-delivery. No second store is introduced.

During execution, the runner atomically replaces one bounded
`.agent/qa/provider-probe-active.json` projection. Its closed content is limited to schema version,
QA invocation ID, provider ID, lifecycle state (`idle|starting|running|terminating|reaping|terminal`),
monotonic elapsed milliseconds, heartbeat UTC timestamp, deadline milliseconds, and last terminal
failure class. It contains no PID, argv, command output, environment, prompt, or credential. The
projection is never acceptance authority. A stale heartbeat is displayed as stale/unavailable and
cannot prove that a provider is alive.

Concurrent host invocations use one nonblocking probe lock. A contender emits `probe_busy`; it does
not attach to, kill, or retry the current owner.

### 3.6 Existing dashboard surface

The existing **Operations -> QA Phase 0 Status** card is extended with these detail rows:

- Active Provider
- Probe State
- Probe Elapsed
- Last Failure Class
- Heartbeat Freshness
- Evidence Invocation

The existing `/api/aistack/aq-qa/run/0` response carries a bounded `provider_probe` projection. No
new endpoint or card is required. The backend treats a missing, malformed, or stale heartbeat as
`unavailable`; it does not infer healthy state from a process list. Provider IDs and failure classes
are low-cardinality; elapsed time and freshness are values, never labels.

## 4. Slice boundaries and exact file ceilings

This PRD and its D0 packet authorize **nothing**. Every later slice requires a new hash-bound design
review, owner activation, independent implementation, and independent acceptance.

### QPPR-C1 — Pure lifecycle contract slice (future; maximum 5 files)

Closed inventory ceiling:

1. `scripts/testing/harness_qa/core/process_lifecycle.py` — pure process-session owner.
2. `config/qa-provider-probe-contract.schema.json` — closed result and heartbeat schemas.
3. `config/qa-provider-probe-policy.json` — provider allowlist and fixed budgets.
4. `scripts/testing/fixtures/qa-provider-probe-vectors.json` — golden lifecycle/failure vectors.
5. `scripts/testing/test-qa-provider-probe-lifecycle.py` — deterministic adversarial tests.

No Phase-0, shell smoke, dashboard, route, Nix, deployment, or live-provider change is allowed in
QPPR-C1.

### QPPR-A1 — Evidence plumbing and host adoption (future; maximum 8 files)

Closed inventory ceiling:

1. `scripts/testing/qa-provider-probe.py` — policy-backed aggregate runner and machine CLI.
2. `scripts/testing/smoke-flagship-cli-surfaces.sh` — compatibility entrypoint; delegates without nested timeout.
3. `scripts/testing/harness_qa/phases/phase0.py` — direct structured adoption for check `0.6.1`.
4. `scripts/testing/harness_qa/core/result.py` — typed details serializer.
5. `scripts/testing/harness_qa/core/context.py` — reserved invocation and interruption state.
6. `scripts/testing/harness_qa/main.py` — reserve-before-context, structured publication, signal re-delivery.
7. `scripts/testing/harness_qa/reporters/json_out.py` — shared typed serialization.
8. `scripts/testing/test-qa-provider-probe-adoption.py` — signal/CLI/Phase-0/evidence parity.

### QPPR-A2 — Existing-card visibility (future; maximum 5 files)

1. `dashboard/backend/api/services/qa_runner.py`
2. `dashboard/backend/api/routes/aistack.py`
3. `dashboard.html`
4. `assets/dashboard.js`
5. `scripts/testing/test-dashboard-qa-provider-probe.py`

A2 must be reviewed and land immediately after A1; neither is complete or activatable alone. Any
new environment variable, endpoint/card, Nix file, registry file, or substitution requires review.

### QPPR-A3 — Optional broker/cgroup convergence (future; inventory not defined)

Only after the agent dispatch broker is live may probe execution move under broker-owned cgroups.
No A2 file or action is authorized or implied here.

## 5. Service Coverage Contract

QPPR-A1/A2 are incomplete unless the following ship together or in immediately consecutive atomic
commits on the same branch:

1. **aq-qa integration:** Phase-0 check `0.6.1` exercises the process helper through the declared
   aggregate runner and preserves typed provider results in immutable QA evidence.
2. **Dashboard visibility:** the existing QA Phase 0 card visibly reports active provider, state,
   elapsed time, heartbeat freshness, last failure class, and evidence invocation; blank `--`
   values when evidence exists are failures.
3. **Runtime path:** the compatibility smoke and direct Phase-0 path use the same policy and result
   normalizer. No shell-only alternate lifecycle remains.

Live validation must include the API response and browser-rendered card. Dashboard-confined Phase 0
continues to skip host-only provider execution; that skip must be visible and must not be normalized
to PASS.

## 6. Threat model and controls

| Threat | Required control |
|---|---|
| Provider reads or blocks on the user's TTY | `stdin=DEVNULL`; no inherited controlling input. |
| Provider stops itself before termination | Group `SIGCONT` before `SIGTERM`, then bounded kill/reap. |
| Provider forks ordinary descendants | New session/process group; group-scoped signals; fork fixture. |
| Orphan survives a parent-only timeout | One lifecycle owner; no nested shorter timeout; terminal reap assertion. |
| PID reuse or unrelated process kill | Signal only the PGID created and retained by the helper; no process search. |
| Shell/argv injection | Closed provider-to-argv policy; argv-only spawn; no shell. |
| Stderr flood or pipe deadlock | Continuous drain; fixed retention caps; truncation is typed failure. |
| Secret/path disclosure in evidence | Sanitization and redaction before bounded retention; no raw output in dashboard/metrics. |
| Duplicate work after a valid failure | Exactly one attempt per provider per invocation; terminal evidence is immutable. |
| Concurrent aggregate probes | Nonblocking owner lock; contender gets `probe_busy`. |
| Forged or stale heartbeat | Heartbeat is a projection; validate closed schema/freshness; immutable QA evidence wins. |
| Provider daemonizes into a new session | `cleanup_failed`, fail closed, no arbitrary process kill; future broker/cgroup gate. |
| Outer caller exits during cleanup | `finally` cleanup and interrupt handling; adversarial outer-timeout fixture verifies no descendant. |
| Dashboard claims host coverage from confinement | Host-only execution remains skipped; card distinguishes unavailable/stale/terminal. |

## 7. Acceptance criteria

### QPPR-C1

- Closed schemas reject unknown fields, provider IDs, lifecycle states, and failure classes.
- Policy validates exact 45/2/1/200-second budgets and four allowlisted provider profiles.
- Clean exit, nonzero exit, executable absence, spawn error, deadline, stopped child, ordinary fork,
  stderr flood, interrupt, concurrent owner, and cleanup-race fixtures map to exactly one result.
- Self-stop and fork fixtures (timeout and leader-exit-0-with-live-child) leave no group member.
- Timeout cleanup records `SIGCONT`, `SIGTERM`, optional `SIGKILL`, and reap in order.
- Real outer SIGTERM/SIGINT prove handler restoration, second-signal coalescing, <=4-second cleanup,
  and cleanup/restoration/single redelivery within 5 seconds. Only the default-terminating fixture
  asserts signal termination/nonzero; returning custom, non-returning custom, and ignored fixtures
  assert preserved post-redelivery semantics without forced exit. Pidfd/`WNOWAIT` tests prove no
  numeric signal after leader reap.
- Valid JSON failure at exit 0/nonzero, malformed/truncated/no output each spawn once and never retry.
- Sanitized stderr is at most 4096 bytes and secrets/control characters do not survive.
- Unit tests do not execute real providers, use the network, mutate the dashboard, or require Nix.

### QPPR-A1/A2

- Direct runner JSON and `aq-qa 0 --machine` represent the same provider result and failure class.
- Compatibility shell entrypoint contains no GNU `timeout`, `--foreground`, `nohup`, `disown`,
  shell-evaluated provider command, or retry loop.
- Phase 0 supplies no parent deadline shorter than the 200-second aggregate contract; Tier-0 remains
  at least 420 seconds.
- Self-stop, fork, forced outer timeout, JSON-machine parity, and no-retry tests pass.
- Forced outer timeout proves the active provider group is continued, terminated, killed if needed,
  and reaped with no stopped/orphan descendant.
- Every attempt is typed immutable evidence bound to the exact reserved heartbeat run ID; later
  success cannot erase failure.
- Heartbeat writes are atomic, bounded, closed-schema-valid, prompt-free, and visibly stale after
  the declared freshness window.
- Existing QA card shows all six detail fields at normal and narrow viewport widths, with accessible
  labels and no console errors.
- `aq-qa 0 --machine`, focused regression tests, Tier-0 pre-commit, Python syntax, shell syntax, JSON
  parsing, and changed-file security checks pass.

## 8. Success metrics

- Zero surviving owned process-group members after every fixture and timed-out probe.
- Zero retries within an invocation; exactly one start event per provider ID.
- 100% provider attempts reach a typed terminal result or `cleanup_failed` before return.
- 100% active probes produce a heartbeat visible in the existing QA card within 2 seconds.
- 100% heartbeat and immutable evidence records validate against the closed contract.
- Zero raw provider output, prompt, credential, PID, argv, or path in metric labels/dashboard detail.
- Machine CLI, Phase-0 result, immutable evidence, API, and rendered dashboard agree on provider ID,
  lifecycle state, and failure class in golden parity tests.

## 9. Rollback

Rollback is commit-scoped and requires separate authorization when it changes a live route.

1. Revert QPPR-A2 first, restoring the five-row card, then revert QPPR-A1.
2. Confirm no probe is active; if one is active, let the lifecycle owner reach terminal cleanup. Do
   not kill by name, argv substring, or registry guess.
3. Revert QPPR-C1 only after all A1/A2 imports and fixtures are gone.
4. Preserve immutable QA evidence and audit history; rollback never deletes or rewrites it.
5. If dashboard visibility fails but process cleanup is correct, retain the helper and disable A1
   activation through a reviewed forward fix rather than restoring unsafe nested timeouts.

## 10. Explicit exclusions

This design does not authorize implementation, staging, commit, deployment, provider execution,
network traffic, service restart, Nix changes, systemd units, cgroups, broker adoption, provider
wrapper changes, credential changes, retries, fallback routing, a new lifecycle store, a new QA
endpoint/card, deletion of evidence, rollback, or any file outside the two later closed inventories.
