# QPPR-C1 pure lifecycle contract implementation authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1-20260718`  
**Idempotency key:** `qa-provider-probe-reliability:c1:pure-lifecycle:v1:20260718`  
**Status:** **PREPARED_ONLY — IMPLEMENTATION NOT AUTHORIZED**  
**Prepared:** 2026-07-18  
**Activation rule:** independent review of this exact authorization is required before the owner may
activate it. A review `PASS`, design acceptance, silence, or broad preauthorization does not activate
the slice. Activation must explicitly name this document's exact SHA-256, one implementer identity,
an activation timestamp, and an expiry no more than 24 hours later.  
**Single use:** activation is consumed by the first complete exact five-file candidate report. An
interrupted attempt without a complete candidate does not consume it, but the same implementer must
resume and reverify all five required absences.

## 1. Bound design chain

This authorization is bound to the following accepted and committed subjects. Any hash mismatch is a
hard stop requiring a new authorization subject and independent review.

| Subject | SHA-256 |
|---|---|
| `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md` | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| `.agents/plans/qa-provider-probe-reliability/D0-DESIGN-PACKET.md` | `041951b9afbb6173e15cc176329f3ae228930199fb67799ad1fb59b32980394f` |
| `.agents/plans/qa-provider-probe-reliability/D0-DESIGN-REVIEW.md` | `9ca904808a903f98398ec9c98113a7f039ef9bb11b4076bfbe4c8a1a133310fb` |

Committed design basis: `b63862ec`. The design review is `PASS` and permits preparation of this
authorization only. C1 remains inactive until the explicit activation record described above.

## 2. Exact five-file implementation ceiling

One bounded implementer must own all five files. Each path must be absent before the first edit.

| # | Operation | Path | Frozen predecessor |
|---:|---|---|---|
| 1 | NEW | `scripts/testing/harness_qa/core/process_lifecycle.py` | must be absent |
| 2 | NEW | `config/qa-provider-probe-contract.schema.json` | must be absent |
| 3 | NEW | `config/qa-provider-probe-policy.json` | must be absent |
| 4 | NEW | `scripts/testing/fixtures/qa-provider-probe-vectors.json` | must be absent |
| 5 | NEW | `scripts/testing/test-qa-provider-probe-lifecycle.py` | must be absent |

A sixth implementation file, an existing-file modification, or substitution of any path is a hard
stop. Documentation, staging, commit, deployment, or adoption work is not part of the candidate.

## 3. Exact implementation grant

### 3.1 Closed schemas and policy

The schema file must use JSON Schema Draft 2020-12 and define closed, independently identifiable v1
objects with every object boundary denying unknown fields. It must cover the provider-probe result,
termination-action evidence, disposition/redelivery evidence, and only the C1 policy/vector objects
needed to validate the pure lifecycle oracle. Unknown versions, fields, providers, profiles,
lifecycle states, results, failure classes, disposition classes, termination actions, and reason
codes must fail closed.

The complete result failure enum is exactly:

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

Success is only `result=pass` with `failure_class=none`. The result contains only the fields accepted
by PRD section 3.2: schema version, invocation ID, closed provider ID, argv profile ID rather than raw
argv, lifecycle state, monotonic timing and deadline, exit code when known, failure class,
termination actions, truncation flags, sanitized stderr summary, disposition/redelivery evidence,
and evidence digest. Prompts, credentials, HOME contents, raw environment, terminal data, arbitrary
paths, full stdout/stderr, PIDs, PGIDs, SIDs, and raw argv are prohibited result fields.

The policy is closed, versioned, immutable data with exactly these initial budgets:

| Budget | Value |
|---|---:|
| provider deadline | 45 seconds |
| SIGTERM grace | 2 seconds |
| SIGKILL reap | 1 second |
| four-provider aggregate | 200 seconds |
| attempts per provider per invocation | 1 |
| sanitized stderr retention | 4,096 bytes |
| stdout protocol-validation retention | 65,536 bytes |

It contains exactly four allowlisted `exit_only` help profiles and no fallback or retry profile:

| Provider ID | Profile ID | Executable | Fixed argv |
|---|---|---|---|
| `codex` | `codex_help` | `codex` | `["codex", "--help"]` |
| `qwen` | `qwen_help` | `qwen` | `["qwen", "--help"]` |
| `claude` | `claude_help` | `claude` | `["claude", "--help"]` |
| `pi` | `pi_help` | `pi` | `["pi", "--help"]` |

C1 may validate these profile declarations but must not execute any real provider. Policy data may
not be overridden by environment variables, CLI flags, fixtures, or model output. A budget change,
new profile, new provider, retry, or fallback requires a new version and independently reviewed
authorization.

### 3.2 Sole process-session owner

`process_lifecycle.py` must be standard-library-only and import-side-effect-free. Its bounded,
argv-only process helper must use `stdin=subprocess.DEVNULL`, continuously drain bounded stdout and
stderr, set `start_new_session=True`, use monotonic deadlines, and never invoke a shell. Tests may
spawn only local deterministic fixture processes created within the test file; the module and tests
must not resolve or execute the four real provider profiles.

Before spawning, the helper must fail closed unless Linux `pidfd_open`, `waitid(...WNOWAIT)`, `/proc`
identity checks, and subreaper support are available. It temporarily enables
`PR_SET_CHILD_SUBREAPER`, preserves the prior value, and restores that value on every branch.
Immediately after spawn it opens the leader pidfd and records PID, PGID, SID, and start time. Direct
exit is observed with `WNOWAIT` and the leader remains unreaped as the identity and PGID anchor until
the final group decision.

Every return path, including direct leader exit zero, must enumerate non-zombie members matching the
recorded PGID and SID, descriptor-bind members where possible, and require two consecutive
all-return quiescent passes. A live descendant after leader exit enters cleanup and returns
`cleanup_failed`. Adopted owned descendants are reaped; unrelated children are never waited or
signalled.

Deadline, interruption, and residual-member cleanup order is exactly:

```text
SIGCONT -> SIGTERM -> 2-second grace -> SIGKILL -> 1-second reap ->
two-pass quiescence -> owned-descendant reap -> leader reap
```

Numeric process-group signals are permitted only while the matching leader remains unreaped and its
pidfd/start-time/PGID/SID identity is valid. They are forbidden after leader reap. `ESRCH` alone is
never proof of exit or quiescence. If pidfd open fails, the helper terminates and reaps only the
demonstrably live direct child and returns `contract_invalid`; it must not issue a later numeric
group signal. No stale PGID, name, argv substring, process search, unrelated PID, or escaped-session
process may be signalled. A provider-like fixture that deliberately escapes to a new session yields
`cleanup_failed`; C1 does not add cgroup ownership.

### 3.3 Outer SIGTERM/SIGINT contract — Revision 3

The main thread blocks SIGTERM and SIGINT with `signal.pthread_sigmask(SIG_BLOCK, ...)` while it
saves exact prior dispositions, installs minimal handlers and a nonblocking wakeup pipe, and commits
process ownership. It then restores the prior mask. Handlers may only record the first signal,
coalesce later signals, and wake the selector. A second signal cannot bypass cleanup or reset the
grace budget.

The first outer signal enters the same idempotent cleanup path as a deadline. Child cleanup is
bounded to four seconds: two seconds for TERM grace, one second for KILL/reap, and one second for
identity/quiescence. One immutable-evidence publication simulation may consume only the remainder of
a five-second cleanup/restoration/redelivery SLO through a bounded worker. The helper then restores
the exact prior handlers and mask, closes wakeup descriptors, and re-delivers the first signal
exactly once. The SLO ends at that redelivery.

With the restored default terminating disposition, the production-path fixture must terminate by
that signal and cannot yield PASS or exit zero. With `SIG_IGN` or an arbitrary custom disposition,
the ignored/handler behavior after redelivery—including return, explicit exit zero, blocking, or
later termination—is outside the helper and the five-second SLO. The helper must not force an exit
after custom or ignored behavior. Result evidence records
`default_terminating|ignored|custom` and redelivery separately from child cleanup. Tests must use
real outer SIGTERM and SIGINT and distinguish default termination, a returning custom handler, a
non-returning custom handler, and an ignored disposition; internal cancellation is insufficient.

### 3.4 Bounded streams and deterministic normalization

Both pipes must continue draining after retention caps are crossed so children cannot deadlock.
Stdout retained only for protocol validation is capped at 65,536 bytes and is absent from results.
Stderr is replacement-decoded as UTF-8, stripped of control characters except newline/tab, redacts
credential-shaped values, reduces path prefixes to declared tokens, and is capped at 4,096 bytes.
Raw output must not reach exception text, logs, metric labels, fixtures, or result fields. Any stream
overflow sets its truncation flag and yields `output_limit_exceeded`; truncated output cannot pass.

Golden vectors must cover both `exit_only` and `machine_json_v1` normalization even though all four
initial provider profiles are `exit_only`. Machine JSON is exactly one closed object with version,
`status=pass|fail`, and a bounded reason code. Precedence is exact: lifecycle failure wins;
truncation becomes `output_limit_exceeded`; empty output becomes `machine_output_missing`;
malformed, multiple, or schema-invalid output becomes `machine_output_invalid`; a valid reported
failure at exit zero or nonzero becomes `provider_reported_failure` with exit code preserved; a
reported pass plus nonzero becomes `exit_nonzero`; and a reported pass plus zero is PASS/`none`.
Every vector asserts `spawn_count=1`. No result may retry.

### 3.5 Required golden and adversarial evidence

The fixture and test must cover at least:

1. clean exit and deterministic closed result;
2. valid nonzero exit recorded once without retry;
3. missing executable and spawn failure;
4. deadline expiry;
5. self-stop proving `SIGCONT` precedes termination;
6. timeout fork and leader-exit-zero fork, with no owned member before return;
7. stderr flood, continuous drain, redaction, control-character removal, and exact cap;
8. interruption during each cleanup phase;
9. concurrent invocation returning `probe_busy` without disturbing the owner;
10. real SIGTERM/SIGINT for default, returning-custom, non-returning-custom, and ignored prior
    dispositions, including second-signal coalescing, handler/mask restoration, <=4-second cleanup,
    and cleanup/restoration/one redelivery within five seconds;
11. exact termination-action order, pidfd/`WNOWAIT` anchoring, two quiescent passes,
    owned-descendant reap, `ESRCH` handling, subreaper restoration, direct-child-reaped races, and no
    numeric signal after leader reap;
12. deliberate new-session escape returning `cleanup_failed` without an arbitrary kill;
13. every closed failure enum and unknown version/field/provider/profile/state/class rejection;
14. output size boundaries and secret/path/control-character canaries; and
15. one-spawn `exit_only` and `machine_json_v1` vectors for all normalization branches.

Tests must be deterministic and offline. They must use local fixture subprocesses only, require no
service or Nix activation, and leave no stopped, zombie, orphaned, or otherwise owned descendant.

## 4. Mandatory stop conditions

The implementer must stop without workaround, extra edits, partial candidate handoff, or inferred
authority if any of these occurs or is needed:

- a sixth changed implementation file, any modification of an existing file, a required NEW path
  already exists, a substituted path, a bound-subject mismatch, or a shared-file conflict;
- any real provider invocation, provider executable resolution, remote/local inference, network,
  traffic, credential, package-manager, or external-service access;
- any Phase-0 registration/import/adoption, compatibility shell edit, shell timeout, shell command
  construction, dashboard/backend/API/HTML/JavaScript edit, runtime import/hook/adoption, service,
  Nix, systemd, environment variable/env-contract change, port, socket, deployment, activation,
  cutover, cleanup of unrelated files, rollback, or deletion;
- any QPPR-A1, QPPR-A2, or QPPR-A3 file or action;
- any store, immutable QA evidence write, heartbeat write, broker, registry, cgroup, worker service,
  daemon, background task, retry, fallback, lifecycle authority outside the direct fixture child, or
  unrelated process wait/signal;
- any shell execution by the lifecycle module, shell-owned timeout, inherited stdin, stale numeric
  PGID signal, leader reap before two-pass quiescence, forced exit after a custom/ignored
  disposition, budget relaxation, policy override, open schema, raw output disclosure, or result
  that claims live provider or operational health.

A stop requires one narrow finding and a separately reviewed amendment. The implementer must not
expand scope or treat owner activation as transitive authority for A1, A2, A3, runtime, or deploy.

## 5. Implementer, review, and integration contract

- Exactly one bounded implementer owns all five files. The implementer may not delegate, split file
  ownership, stage, commit, deploy, activate, or accept its own work.
- Before editing, the implementer records its identity and verifies all three bound hashes and all
  five required absences. It preserves every unrelated dirty file.
- The complete candidate report contains all five exact hashes, concise objective/root cause,
  important implementation reasoning and tradeoffs, exact validation commands/results, and explicit
  exclusions. The first such report consumes the activated authorization.
- A different agent/session independently reviews the exact five-file candidate. It records its
  role/model, all subject hashes, challenges every stop condition and lifecycle race, verifies real
  outer-signal and descendant-cleanup evidence, and issues one final
  `VERDICT: PASS|FAIL|REQUEST_REVISION`.
- A reviewer that changes any candidate byte becomes a material rewriter and is recused from
  accepting the new subject. Any changed candidate hash requires fresh independent review.
- Only the orchestrator may stage and commit, and only after an exact-subject independent `PASS`,
  focused lifecycle tests, Python compilation, JSON parsing and Draft-2020-12 validation, changed-file
  security checks, `aq-qa 0 --machine`, and
  `scripts/governance/tier0-validation-gate.sh --pre-commit` pass.
- No candidate, test, review, stage, or commit activates A1/A2, a provider run, Phase 0, runtime,
  dashboard, service, deployment, traffic, cutover, rollback, or later work.

## 6. Acceptance evidence required for PASS

The independent implementation reviewer may issue `PASS` only when all are true:

1. The subject is exactly five NEW files, all predecessor absences were verified, and no existing
   file changed under this grant.
2. All v1 objects are Draft-2020-12 closed schemas and every unknown version, field, provider,
   profile, lifecycle state, result, class, disposition, action, and reason is rejected.
3. The policy encodes exactly 45/2/1/200 seconds, one attempt, 4,096/65,536-byte retention, and the
   four fixed `codex|qwen|claude|pi` `--help` `exit_only` profiles without overrides.
4. Spawn is argv-only with stdin DEVNULL and a fresh session, and pipes remain drained after caps.
5. pidfd/`WNOWAIT`/start-time/PGID/SID/subreaper ownership, all-return two-pass quiescence, exact
   `SIGCONT -> SIGTERM -> grace -> SIGKILL -> reap`, and no-signal-after-reap invariants pass under
   stopped, forked, raced, and `ESRCH` fixtures.
6. Real SIGTERM/SIGINT tests prove Revision-3 handler/mask restoration and one redelivery; only the
   default disposition guarantees termination/nonzero, and custom/ignored behavior is preserved
   without a forced exit.
7. Closed results, failure precedence, bounded redacted stderr, secret/path/control canaries, and
   one-spawn `exit_only`/`machine_json_v1` normalization vectors pass.
8. Tests leave no owned live, stopped, zombie, or orphan descendant and access no real provider,
   inference endpoint, network, service, Phase 0, dashboard, Nix, broker, store, or cgroup.
9. Focused tests, Python compilation, JSON parsing/schema validation, changed-file security checks,
   `aq-qa 0 --machine`, and Tier-0 pass without provider or network execution by C1.
10. The implementation and evidence make no live-provider, operational-health, adoption, runtime,
    service, deployment, traffic, cutover, cleanup, rollback, or later-slice claim.

## 7. Activation and consumption record

Current activation state: **NOT ACTIVATED**.

After an independent authorization review passes this exact document, the owner may activate C1 only
by explicitly naming:

- this authorization's exact SHA-256;
- exactly one implementer identity;
- an activation timestamp and an expiry no more than 24 hours later; and
- confirmation that the exact five-file ceiling and every stop condition remain unchanged.

Until that explicit record exists, no file in section 2 may be created under this grant.

`RECORD: PREPARED_ONLY. QPPR-C1 implementation, real provider execution, network, Phase 0, shell,
dashboard, runtime adoption, A1/A2/A3, services, Nix, deployment, traffic, cutover, cleanup, rollback,
staging, and commit remain unauthorized.`
