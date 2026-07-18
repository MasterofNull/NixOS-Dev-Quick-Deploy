# QPPR C1A and A1/A2 preparation — independent review

**Overall verdict:** **REQUEST_REVISION**
**Reviewed:** 2026-07-18
**Role:** independent architecture, security, SRE, QA, and dashboard-contract reviewer
**Implementation authority:** none

## Exact reviewed subjects

| Subject | Verified SHA-256 | Verdict |
|---|---|---|
| `C1A-CONTRACT-AMENDMENT-DESIGN-PACKET.md` | `d6cb56fb81f854ce7a1ffa326700f338406930dd0356291b874be022c8425e9d` | **PASS** |
| `C1A-IMPLEMENTATION-AUTHORIZATION.md` | `76eefcb29970917c7f211fe1165fcb96524045814a89204304e06db8733055ac` | **PASS / remains PREPARED_ONLY** |
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `53a780def3cf4520469ab48715cf2e35f903023a8ee5c939de3bc96ccc517080` | **REQUEST_REVISION** |
| `A1-IMPLEMENTATION-AUTHORIZATION.md` | `d9d0251e8c7a63ad320d11204f049b75cf0d10d358c1b7e595f4cb8088d28dcb` | **REQUEST_REVISION / correctly not activatable** |
| `A2-IMPLEMENTATION-AUTHORIZATION.md` | `596feb4ad57a19eb1c7a4215220ba9711668daca4c6fbdd96e99106998dec24e` | **REQUEST_REVISION / correctly not activatable** |

All five hashes matched the frozen review request. All ten existing A1/A2 predecessor hashes also
matched the candidate tables, both declared NEW test/runner paths were absent, and none of the
implementation target paths had a dirty-worktree overlap at review time.

## C1A adjudication — PASS

C1A is the minimal non-breaking correction for the missing active-probe projection schema. Its
two-file ceiling changes only the accepted contract schema and its offline lifecycle contract test.
The closed eight-field object, conditional provider/state/failure relationships, forbidden-field
tests, exact predecessor binding, separate activation requirement, independent acceptance, and
rollback/stop rules preserve every accepted C1 result, policy, vector, budget, and runtime boundary.
It adds no heartbeat writer, provider resolution, Phase-0 adoption, evidence mutation, dashboard
surface, route, deployment, or live action.

The owner may activate C1A only by the exact mechanism in its authorization. This review does not
activate it. A nonblocking implementation note is to enforce the intended UTC representation
explicitly (format checking plus a terminal `Z` requirement) instead of relying on an annotation
alone; the packet's malformed-time rejection requirement is otherwise sufficient.

## Blocking A1/A2 findings

### R1 — Accepted C1 cannot emit the required live lifecycle transitions

The A1 packet requires an invocation-bound heartbeat at each state transition and at least once per
second while running, including `terminating` and `reaping`. The accepted
`run_owned_process(...)` signature has no heartbeat/state-observer parameter. Its lifecycle state is
internal, and its public result appears only after terminal cleanup. It also requires the main
thread for signal ownership, so A1 cannot move it to a worker merely to keep a heartbeat controller
in the main thread. A periodic A1 thread could truthfully repeat `running`, but it cannot observe or
truthfully publish the internal terminating/reaping transitions. The PRD's conceptual helper API did
include `heartbeat`; the accepted implementation did not.

**Required revision:** freeze and independently review a pure C1B interface correction before A1.
It must expose a bounded, exception-contained state-observation contract for
`starting|running|terminating|reaping|terminal`, define how observation cannot delay the four/five-
second cleanup/redelivery SLO, and add adversarial tests for observer failure, blocking, ordering,
and no post-terminal emission. Rebind A1 to the accepted C1B commit and exact helper/test hashes.
Do not fake terminating/reaping state in the A1 writer.

### R2 — The aggregate ownership lock is not frozen as a cross-process security contract

The C1 `_INVOCATION_LOCK` is a process-local `threading.Lock` and is released after each provider.
A1 correctly calls for one aggregate lock across all four providers, but the packet does not specify
an interprocess stable-inode lock, its symlink/ownership rules, or its lifetime across heartbeat
publication and all four attempts. Two separate `aq-qa`/compatibility processes could otherwise
both pass a Python-only lock and execute overlapping aggregates.

**Required revision:** freeze one repository-bound lock path and a nonblocking OS advisory-lock
algorithm using a symlink-safe, regular, stable inode. Hold it from admission through the final
terminal heartbeat/publication boundary; never replace or unlink the locked inode. Define exact
`probe_busy` aggregate evidence (four ordered no-spawn results or one separately closed aggregate
result), invocation binding, and lock-release behavior for normal, exception, and redelivered-signal
paths. Add a real two-process contender fixture. No contender may write the owner's heartbeat or
signal/attach/retry.

### R3 — The dashboard transport cannot meet five-second freshness or two-second visibility as written

The current card calls `loadQA()` but has no periodic `loadQA` schedule. The existing
`/aistack/aq-qa/run/0` GET is an active QA-run/cache route with a 300-second cache, not a passive
heartbeat subscription. Merely attaching `provider_probe` to its responses cannot make an external
host probe visible within the PRD's two-second target, and normal dashboard refresh cadence cannot
keep a one-second heartbeat current under the frozen five-second freshness threshold. Blindly
polling the current GET would also repeatedly interact with the QA execution route.

**Required revision:** within the existing endpoint ceiling, freeze a passive projection-only mode
(for example, a validated query mode on `/aq-qa/run/0`) that never starts QA, mutates cache/evidence,
or executes a provider. Specify bounded client polling at no more than two seconds while an active
projection is expected, an idle/backoff/terminal stop policy, request cancellation, and stale/error
rendering. Tests must prove an externally started fake host heartbeat reaches the DOM within two
seconds without causing a dashboard-confined QA execution. If a passive mode cannot be made clear
and non-mutating on this route, the parent PRD's no-new-endpoint decision requires explicit revision
rather than an implicit monitoring gap.

### R4 — Typed evidence has no frozen aggregate `details` shape

The packet says `CheckResult.details` is schema-tagged and that check `0.6.1` contains ordered
provider results, but it does not freeze whether `details` is a list, an envelope, or another
object. The accepted schema closes individual `qa.provider-probe-result.v1` records only. Leaving
the aggregate shape implicit permits reporter/evidence/API drift and weakens the promised byte-for-
structure parity.

**Required revision:** define one exact bounded representation. The minimal option is an exact
four-item list in policy order whose every item independently validates as
`qa.provider-probe-result.v1`; otherwise add a closed versioned aggregate envelope in a reviewed
contract amendment. Freeze how partial interruption and aggregate `probe_busy` are represented and
require the shared serializer, immutable evidence, JSON reporter, and tests to preserve that exact
shape.

## Boundaries that passed review

- The A1 maximum-eight and A2 maximum-five inventories match the parent PRD exactly.
- A1 and A2 remain separate atomic commits, consecutive on one branch, with no claim that either
  alone satisfies service coverage or activates provider execution.
- Reserve-before-context identity, single-attempt normalization, bounded output, fake-provider-only
  implementation validation, immutable-evidence authority, and projection non-authority are sound.
- The heartbeat/API vocabularies exclude raw output, prompts, credentials, process identifiers,
  argv, environment, arbitrary paths, model identity, and acceptance verdicts; provider/state/class
  labels are closed and low-cardinality.
- A2 reuses the existing route and card, keeps host-only dashboard execution as explicit SKIP, uses
  text-only DOM rendering, and requires desktop/narrow accessibility and canary-exclusion tests.
- The paired rollback order, no-kill-by-guess rule, no live provider/deployment during implementation,
  independent review, no self-activation, and explicit stop conditions are appropriate.

## Validation evidence

- Frozen candidate SHA-256 verification: **PASS, 5/5 exact**.
- Existing A1/A2 predecessor SHA-256 verification: **PASS, 10/10 exact**.
- Candidate target dirty-overlap scan: **PASS, none**.
- Accepted C1 focused lifecycle suite:
  `python3 scripts/testing/test-qa-provider-probe-lifecycle.py` — **PASS, 27/27 in 48.546 s**.
- Static executable-interface inspection: **confirmed** no public heartbeat/state observer in
  `run_owned_process`, main-thread signal ownership, and only a terminal result return.
- Static dashboard-path inspection: **confirmed** 300-second QA cache, an active `/aq-qa/run/0`
  route, and no scheduled `loadQA` poll.

## Gate decision

`VERDICT: REQUEST_REVISION` for the package as a whole. C1A design and authorization independently
PASS and may proceed through explicit owner activation. A1/A2 remain correctly blocked and must not
be activated until R1-R4 are resolved, rebound to accepted predecessor hashes, and independently
reviewed. This review authorizes no implementation, staging, commit, heartbeat/evidence write,
provider execution, network, API/browser action, deployment, traffic, rollback, or deletion.
