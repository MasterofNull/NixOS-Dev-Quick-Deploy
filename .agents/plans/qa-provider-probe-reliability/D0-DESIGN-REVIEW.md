# QA Provider Probe Reliability D0 Revision 3 — Independent Design Review

Verdict: **PASS**  
Reviewed: 2026-07-18  
Review role: independent architecture, security, SRE, and process-lifecycle reviewer  
Implementation authority: **None**

## Reviewed subjects

- `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md`  
  SHA-256: `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d`
- `.agents/plans/qa-provider-probe-reliability/D0-DESIGN-PACKET.md`  
  SHA-256: `041951b9afbb6173e15cc176329f3ae228930199fb67799ad1fb59b32980394f`

The hashes match the requested Revision 3 subjects. This PASS permits preparation of a separate,
hash-bound QPPR-C1 authorization only. It does not activate C1, A1, A2, provider execution,
implementation, staging, commit, deployment, traffic, rollback, or any live-system action.

## R1 and R5 — Outer-signal cleanup and disposition-specific redelivery: resolved

The design now has one executable signal contract:

- SIGTERM/SIGINT are blocked while prior dispositions are saved and minimal handlers plus a
  nonblocking wakeup path are installed.
- The first signal selects one idempotent cleanup path; later signals are coalesced and cannot
  bypass cleanup or reset the grace budget.
- Child cleanup is bounded to four seconds. One immutable-evidence publication attempt may use only
  the remainder of the five-second cleanup/restoration/redelivery SLO.
- Prior masks and dispositions are restored and the first signal is re-delivered exactly once. The
  SLO ends at redelivery, not at arbitrary post-redelivery handler completion.
- Only the restored default terminating disposition guarantees signal termination and a nonzero
  outcome. Returning, blocking, or exiting custom handlers and `SIG_IGN` retain their original
  semantics outside the helper and outside that SLO; the helper does not force an exit.
- Evidence independently records disposition class and redelivery, and real-signal fixtures
  distinguish default termination, returning custom, non-returning custom, and ignored behavior.

This resolves the prior impossible requirement to preserve an arbitrary disposition while also
controlling its eventual duration and exit status. Internal cancellation alone is explicitly
insufficient for acceptance.

## R2 — Process identity, descendants, and terminal quiescence: remains resolved

The helper preflights pidfd, `waitid(...WNOWAIT)`, `/proc` identity, and subreaper support. The
unreaped zombie leader anchors the numeric PGID while PID/PGID/SID/start time and pidfd identity are
retained. Every return, including leader exit zero, requires two consecutive non-zombie group
quiescence observations. Residual ordinary descendants enter bounded cleanup and force
`cleanup_failed`; adopted owned descendants are reaped while unrelated children are not.

`SIGCONT -> SIGTERM -> grace -> SIGKILL -> quiescence -> owned-descendant reap -> leader reap` is
the frozen order. Numeric group signals are prohibited after leader reap, and `ESRCH` is never sole
proof. A process outside the helper-created session cannot join its group, so group `SIGCONT` is
appropriately bounded while the descriptor/start-time identity remains valid. Timed-out and
zero-exit fork fixtures, no-signal-after-reap checks, and subreaper restoration make the invariant
testable. Deliberate new-session escape remains an acknowledged `cleanup_failed` boundary for
future broker/cgroup ownership.

## R3 — Immutable evidence, invocation identity, and service coverage: remains resolved

The existing immutable QA store remains the sole authority. `main.py` reserves the real invocation
before `RunContext`; that exact identity reaches Phase 0, the runner, and the bounded heartbeat.
Schema-tagged `CheckResult.details` passes through one shared serializer into JSON and immutable
evidence. JSON hidden in human description/reason text is forbidden, and standalone compatibility
execution cannot invent a canonical invocation or write its heartbeat.

The later inventories remain exact and bounded:

- C1: five pure lifecycle contract/schema/policy/vector/test files;
- A1: eight host-adoption, typed-result, context, main, reporter, and parity-test files;
- A2: five existing API/card visibility and browser-test files.

A1 and A2 must land immediately consecutively on one branch and neither is accepted or activatable
alone. The existing `/api/aistack/aq-qa/run/0` response and existing QA Phase 0 card remain the only
surface. Dashboard confinement preserves host-only execution as SKIP/unavailable, never PASS.

## R4 — Deterministic one-spawn normalization: remains resolved

Profiles explicitly select `exit_only` or `machine_json_v1`. Lifecycle failure has precedence;
truncation, missing output, malformed/multiple/schema-invalid output, valid reported failure at
zero/nonzero exit, pass plus nonzero, and pass plus zero each have one closed result mapping. Every
golden vector asserts `spawn_count=1`; no result triggers an in-invocation retry. Direct runner,
Phase-0 typed evidence, immutable evidence, API projection, and rendered DOM parity remain required.

## Architecture, security, and SRE findings

- `stdin=DEVNULL`, argv-only allowlisted execution, declared cwd/environment, continuous pipe
  draining, and no shell interpolation correctly close TTY, injection, and pipe-deadlock paths.
- The result/failure enum and heartbeat contract are closed. Retained stderr is sanitized and
  bounded to 4096 bytes; retained protocol stdout is bounded to 65,536 bytes; overflow is drained
  and cannot pass.
- Raw output, prompts, credentials, PID, argv, environment, and arbitrary paths remain excluded
  from heartbeat, default dashboard data, logs, and metric labels.
- The 45/2/1/200/210/420 budget hierarchy is internally ordered: four worst-case 48-second
  lifecycles plus eight seconds equal the aggregate ceiling, which remains below host and Tier-0
  bounds.
- A nonblocking aggregate lock and `probe_busy` prevent duplicate work without allowing a contender
  to attach, signal, retry, or mutate the owner.
- Immutable evidence outranks the heartbeat. Missing, malformed, stale, or forged heartbeat data is
  unavailable and cannot prove health or acceptance.
- Required self-stop, both fork branches, real outer signals, cleanup-phase interrupts,
  descriptor-bound reap, machine normalization, stale heartbeat, JSON parity, and browser tests are
  sufficient for later slice acceptance.

## Nonblocking editorial notes

Before any future A3 design review, correct two stale labels in the PRD: “No A2 file or action” under
the A3 section should read “No A3 file or action,” and “outside the two later closed inventories”
should reflect the three defined future inventories. These phrases are restrictive rather than
permission-granting, do not weaken the C1 boundary, and therefore do not block this D0 PASS.

## Gate decision

Revision 3 resolves R5 and retains the R1–R4 corrections. The design is internally coherent,
bounded, observable, independently testable, and explicitly non-activating. A separately prepared
QPPR-C1 authorization must bind the accepted PRD, packet, exact five-file inventory, and this PASS;
owner activation and independent implementation acceptance remain mandatory.

