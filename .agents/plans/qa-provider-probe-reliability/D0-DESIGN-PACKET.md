# QA Provider Probe Reliability D0 — Design Packet

Status: **PREPARED_ONLY / DESIGN_ONLY / REVISION 3 / UNAUTHORIZED**  
Prepared: 2026-07-18  
Parent PRD: `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md`  
Implementation authority: **None**

Revision 2 resolves independent review `D0-DESIGN-REVIEW.md` SHA-256
`355d3017c18daa9bb6e5b82cb2240801bfc5be2013ee8b3fc46492f81d4c71af` R1-R4.

Revision 3 resolves sole remaining R5 from review SHA-256
`1ef328c095a90959f4764ae4e20f28e8373205209b2eff33ccacaf7850da0dd8` by ending the
five-second SLO at cleanup, restoration, and one redelivery and separating default termination from
preserved custom/ignored post-redelivery behavior.

## 1. Decision requested

Independently review and either accept or request revision of the QA provider-probe reliability
architecture. D0 freezes only the root-cause statement, contracts, budgets, threat controls, later
slice ceilings, and acceptance requirements. It does not permit an implementation candidate.

## 2. Frozen evidence

The current Phase-0 provider path has three nested owners with incompatible semantics:

```text
Tier-0: timeout --foreground 420s aq-qa 0
  -> Phase 0: cmd_ok(... timeout=15s)
     -> aggregate shell: 4 sequential providers x 45s
        -> timeout --foreground 45s <provider> --help
```

Concrete observations frozen by this packet:

1. `scripts/testing/harness_qa/core/helpers.py::cmd_ok` defaults to a 15-second
   `subprocess.run()` timeout, captures output, and does not set stdin, a new session, or a process
   group.
2. `scripts/testing/harness_qa/phases/phase0.py::_check_flagship_cli` uses that default for
   `scripts/testing/smoke-flagship-cli-surfaces.sh`.
3. The smoke declares 45 seconds per command and serially probes `codex`, `qwen`, `claude`, and
   `pi`; its nominal provider-only aggregate is 180 seconds.
4. The smoke uses `timeout --foreground` for each provider. The 15-second Python timeout owns only
   its direct shell child and cannot prove cleanup of the foreground timeout/provider descendants.
5. Stdin remains attached. A TTY-reading, self-stopping, or forking provider can be stopped or
   orphaned when the parent-only timeout fires.
6. `cmd_ok` collapses nonzero exit, missing executable, timeout, and OS error to one boolean. A
   caller can retry a resultless aggregate and repeat providers whose nonzero failure was already
   valid terminal evidence.
7. Tier-0's 420-second ceiling is adequate in total but cannot compensate for the inner 15-second
   cutoff. The dashboard-confined Phase 0 correctly treats provider CLI checks as host-only.

Root cause: **nested incompatible timeout, process-group, stdin, and TTY ownership contracts, plus
an inner parent budget that is shorter than one provider budget and twelve times shorter than the
four-provider nominal aggregate.**

## 3. Frozen architecture

### 3.1 Lifecycle helper

One small standard-library Python helper becomes the sole lifecycle owner for a bounded argv
process. It must use:

- `stdin=DEVNULL`;
- `start_new_session=True` and the created process group as the only signal target;
- continuous bounded stdout/stderr drain;
- monotonic deadlines;
- `SIGCONT -> SIGTERM -> 2-second grace -> SIGKILL -> 1-second reap` on timeout or interruption;
- a `finally` cleanup path and idempotent `ESRCH` handling;
- no shell, provider retry, PID/name search, network, or unrelated process signal.

The helper preflights pidfd, `waitid(...WNOWAIT)`, `/proc` identity, and subreaper support. It opens
the leader pidfd and records PID/PGID/SID/start time immediately after spawn. Exit is observed
without reaping; the zombie leader anchors the PGID until two consecutive enumeration passes prove
no non-zombie group member. This check precedes every return, including exit 0. A live descendant
forces cleanup and `cleanup_failed`; adopted owned descendants are reaped. Numeric PGID signals are
allowed only while the unreaped leader identity remains descriptor-bound and are forbidden after
reap. `ESRCH` is never sufficient proof.
No kill by stale numeric PGID is permitted under any branch.

The main thread uses `signal.pthread_sigmask(SIG_BLOCK, ...)` to block SIGTERM/SIGINT during handler/wakeup-pipe installation, then restores its
mask. Handlers only record the first signal, coalesce later signals, and wake the selector. The first
signal drives the one cleanup path; another cannot bypass or reset it. Cleanup is bounded to 4
seconds. A single immutable-evidence attempt may use only the remainder of a five-second
cleanup/restoration/redelivery SLO. Prior handlers/mask are then restored and the first signal is
re-delivered exactly once; the SLO ends at redelivery. A restored default terminating disposition
must terminate by signal and cannot yield PASS/exit 0. For ignored or custom dispositions, subsequent
return, exit, block, or termination is outside the helper and SLO; no forced exit overrides it.
Evidence separately reports disposition class and redelivery. Real-signal tests distinguish default
termination, returning custom, non-returning custom, and ignored behavior.

### 3.2 Closed failure enum

The complete v1 values are:

```text
none | executable_missing | spawn_failed | exit_nonzero | provider_reported_failure |
machine_output_missing | machine_output_invalid | deadline_exceeded | output_limit_exceeded |
cleanup_failed | interrupted | probe_busy | contract_invalid
```

Unknown values and fields fail schema validation. Retained stderr is sanitized and limited to 4096
bytes. Retained stdout is limited to 65,536 bytes for validation and is absent from heartbeat and
dashboard detail. Overflow is drained but returns `output_limit_exceeded`.

### 3.3 Frozen budgets

| Item | Frozen v1 value |
|---|---:|
| Per provider | 45 s |
| TERM grace | 2 s |
| KILL reap | 1 s |
| Four-provider aggregate | 200 s |
| Phase-0 allowance for aggregate | >= 210 s |
| Tier-0 outer Phase-0 allowance | >= 420 s |
| Attempts per provider per invocation | 1 |
| Heartbeat update SLO | <= 2 s |
| Sanitized stderr retained | <= 4,096 bytes |
| Stdout retained for validation | <= 65,536 bytes |

The dashboard-confined runner does not execute host provider probes. No override may raise these
values in QPPR-C1, QPPR-A1, or QPPR-A2; a budget change requires a new reviewed contract version.

Profiles declare `exit_only` or `machine_json_v1`. For machine JSON: lifecycle failure wins;
truncated maps to `output_limit_exceeded`; empty to `machine_output_missing`; malformed/multiple/
invalid to `machine_output_invalid`; valid fail at exit 0/nonzero to
`provider_reported_failure`; pass plus nonzero to `exit_nonzero`; pass plus zero to PASS. Every
vector asserts `spawn_count=1`; normalization never retries.

### 3.4 Evidence and visibility

- The existing immutable QA store remains authority. `main.py` reserves before `RunContext`; exact
  run ID/sequence/start time reach the runner. Schema-tagged `CheckResult.details` flows through one
  shared serializer into JSON and immutable evidence. JSON in description/reason is forbidden.
- `.agent/qa/provider-probe-active.json` is a bounded atomic current-state projection containing no
  PID, argv, output, prompt, environment, path, or credential. It uses only the actual reserved run
  ID; standalone execution neither writes it nor invents an invocation.
- The existing `/api/aistack/aq-qa/run/0` response may expose the validated projection.
- The existing **QA Phase 0 Status** card gains Active Provider, Probe State, Probe Elapsed, Last
  Failure Class, Heartbeat Freshness, and Evidence Invocation rows. There is no new endpoint/card.

## 4. Later slices — closed ceilings

### QPPR-C1: pure contract (maximum 5 files)

1. `scripts/testing/harness_qa/core/process_lifecycle.py`
2. `config/qa-provider-probe-contract.schema.json`
3. `config/qa-provider-probe-policy.json`
4. `scripts/testing/fixtures/qa-provider-probe-vectors.json`
5. `scripts/testing/test-qa-provider-probe-lifecycle.py`

No adoption or live provider execution belongs in C1.

### QPPR-A1: evidence plumbing and host adoption (maximum 8 files)

1. `scripts/testing/qa-provider-probe.py`
2. `scripts/testing/smoke-flagship-cli-surfaces.sh`
3. `scripts/testing/harness_qa/phases/phase0.py`
4. `scripts/testing/harness_qa/core/result.py`
5. `scripts/testing/harness_qa/core/context.py`
6. `scripts/testing/harness_qa/main.py`
7. `scripts/testing/harness_qa/reporters/json_out.py`
8. `scripts/testing/test-qa-provider-probe-adoption.py`

### QPPR-A2: existing-card visibility (maximum 5 files)

1. `dashboard/backend/api/services/qa_runner.py`
2. `dashboard/backend/api/routes/aistack.py`
3. `dashboard.html`
4. `assets/dashboard.js`
5. `scripts/testing/test-dashboard-qa-provider-probe.py`

A2 lands immediately after A1; neither is complete or activatable alone. New env, endpoint/card,
Nix, registry, wrapper, or substituted files exceed D0.

Any new environment variable, endpoint, card, Nix/systemd/cgroup file, provider wrapper, or file
substitution exceeds D0 and stops the slice.

## 5. Required test inventory

QPPR-C1 and A1 acceptance must collectively include:

1. clean exit and deterministic result;
2. valid nonzero exit recorded once with **no retry**;
3. missing executable and spawn error;
4. deadline expiry;
5. **self-stop** fixture proving `SIGCONT` precedes termination;
6. **fork** fixtures proving timeout and leader-exit-0 descendants are gone before return;
7. stderr flood proving continuous drain, sanitization, and cap;
8. interrupt during each cleanup phase;
9. concurrent invocation returning `probe_busy` without disturbing the owner;
10. real outer SIGTERM/SIGINT proving handler restoration, second-signal coalescing, <=4-second
    cleanup, cleanup/restoration/single redelivery within 5 seconds, and no child survivor; only
    default disposition asserts termination/nonzero, while returning custom, non-returning custom,
    and ignored fixtures assert preserved behavior with no forced exit;
11. exact signal/action ordering and terminal reap;
12. **JSON-machine parity** between direct runner, Phase-0 mapping, immutable evidence, API, and
    dashboard projection;
13. malformed/unknown schema data rejection;
14. stale heartbeat shown as unavailable, never healthy;
15. valid machine failure at exit 0/nonzero, malformed, truncated, and no output, each exactly one
    spawn with frozen class and no retry;
16. pidfd/`WNOWAIT` anchor, two quiescence passes, descendant reap, and no numeric signal after reap;
17. browser card detail at normal/narrow viewport with accessible labels and no console errors.

Tests use fake processes only until a separately authorized A1 live canary. They do not call remote
providers, inference endpoints, package managers, or the network.

## 6. Service coverage gate

A1/A2 cannot be accepted unless all three are present in immediately consecutive
atomic commits on one branch:

- Phase-0 `0.6.1` integration exercises the shared runner and publishes immutable evidence;
- the existing QA card renders the active-provider heartbeat and terminal evidence detail;
- the shell compatibility surface and Python Phase-0 surface produce the same typed result.

Live acceptance includes `aq-qa 0 --machine`, the focused tests, Tier-0 23/23, the existing API, and
a browser check. A dashboard-confined host-only skip remains SKIP and is never relabeled PASS.

## 7. Threat review prompts

The independent reviewer must explicitly adjudicate:

- whether group `SIGCONT` can affect anything outside the helper-created session;
- stopped child, zero-exit fork, `ESRCH`, PID/PGID reuse, pidfd/`WNOWAIT` anchoring, subreaper
  restoration, and direct-child-reaped races;
- pipe-flood behavior after retention limits are reached;
- parent interruption during TERM grace and KILL reap;
- default/custom/ignored outer dispositions, separate post-redelivery semantics, and second-signal behavior;
- a provider that deliberately creates a new session;
- heartbeat forgery/staleness and immutable-evidence precedence;
- secret/path/control-character leakage through stderr, API, DOM, logs, and metrics;
- duplicate aggregate invocations and valid-failure retry;
- the exact 45/2/1/200/210/420 budget ordering;
- dashboard-safe behavior and whether it could falsely claim host provider coverage.

## 8. Acceptance decision

D0 passes only if an independent reviewer confirms:

1. the evidence supports the stated root cause;
2. one helper owns spawn, signal, cleanup, and reap;
3. the failure enum and schemas are closed;
4. budgets are internally ordered and leave cleanup margin;
5. evidence ownership remains singular and immutable;
6. heartbeat is explicitly a non-authoritative projection;
7. service coverage uses the existing QA API/card;
8. all later inventories are exact and bounded with typed serializer/invocation plumbing;
9. self-stop, zero-exit fork, real outer signals, normalization/parity, and no-retry are mandatory;
10. no wording can be interpreted as live implementation or provider authority.

Verdict format: `PASS`, `REQUEST_REVISION`, or `BLOCKED`, with subject hashes and concrete findings.
Only a PASS permits preparation of a separate hash-bound QPPR-C1 authorization. It does not activate
C1.

## 9. Rollback and exclusions

D0 has no runtime rollback because it changes no runtime. Future rollback is reverse-order A2 then
A1 then C1, preserves immutable evidence, and never kills processes by name/argv or deletes history.

Explicitly excluded: implementation, staging, commit, deployment, provider invocation, traffic,
network use, service restart, Nix/systemd/cgroup work, broker cutover, wrapper changes, retries,
fallbacks, credential changes, new state authority, new API endpoint/card, deletion, cleanup of
unrelated files, and rollback.
