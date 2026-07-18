# QPPR-A1/A2 — Host adoption and existing-card visibility design

Status: **PREPARED_ONLY / DESIGN_ONLY / REVISION 3 / BLOCKED ON C1A+C1B / UNAUTHORIZED**
Prepared: 2026-07-18
Parent PRD: `.agent/PROJECT-QA-PROVIDER-PROBE-RELIABILITY-PRD.md`
Accepted lifecycle predecessor: commit `19c78faaf5ab6d3635ac05a80fd5ba3c63cb1aae`
Prerequisites: accepted and committed QPPR-C1A heartbeat contract and QPPR-C1B lifecycle observer

Revision 2 resolves independent preparation review SHA-256
`dc1f2a3835291c7a587e33c5a3096b09a5f4610d816cd1d9a51dd1abda651b92` R1-R4: truthful
descriptor-only lifecycle observation, stable-inode cross-process aggregate admission, passive
projection polling independent of the 300-second QA cache, and one exact four-result details shape.

Revision 3 resolves the two narrow remaining findings in independent review SHA-256
`26e74adc45dd69b8ef88b95109c21d69cb07adb33c5cebeb51952affdf6c9fa4`: one idempotent
terminal-event/result join covers ordinary and signal-redelivery paths, and C1B validates the
observable `FD_CLOEXEC` property rather than claiming descriptor provenance. Revision-2 locking,
passive transport/polling, and details-shape contracts remain unchanged.

## 1. Outcome and scope

A1 replaces the three-owner provider smoke path with the accepted C1 lifecycle owner, binds typed
provider results to the immutable QA invocation, and publishes one bounded current-state projection.
A2 projects that state through the existing Phase-0 response and the existing **QA Phase 0 Status**
card. The slices retain separate atomic commits but must land consecutively on the same branch;
neither may be accepted, activated, deployed, or called complete alone.

This packet preserves the current dashboard's compact industrial operations language. It adds six
accessible data rows to the existing card and no new visual system, panel, route, control, animation,
dependency, or static-art asset. The current architecture graph confirms the intended dependency
chain: `phase0.py` produces QA results; `qa_runner.py` executes/normalizes them;
`aistack.py` imports that service and owns `/aq-qa/run/{phase}`; `assets/dashboard.js` fetches
`/aistack/aq-qa/run/0`; and `dashboard.html` owns the existing card DOM.

## 2. Bound design and implementation subjects

| Subject | SHA-256 |
|---|---|
| PRD | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| D0 packet | `041951b9afbb6173e15cc176329f3ae228930199fb67799ad1fb59b32980394f` |
| D0 review | `9ca904808a903f98398ec9c98113a7f039ef9bb11b4076bfbe4c8a1a133310fb` |
| C1 authorization | `d4c574ddecd21c5f88e501806cde7593bb3fb1b4c59c003d3479d1527b035743` |
| C1 authorization review | `eccd72ab06cec92a0be6759484ce2541198a28cc0eea929bcdb58b5a1c4c0fd4` |
| C1 implementation acceptance | `3f084c8af9ce53aced4ab40a190688756ed547954262a2277324bdccb541599c` |
| C1 process owner | `d458b1044850b336374745c28254a808aba153b16225eedb82396873bc844170` |
| C1 schema before C1A | `afe2a2aa5c6de4fed87a224d8aa845317d5e734d9403e68ff164a98ca6544756` |
| C1 policy | `2cbe6e350f35cd9e0831186df31f9631a10c1e838fb0246fc1f56828abb4a6af` |

The A1 authorization cannot be activated until a new amendment binds the exact accepted C1A and
C1B commits, implementation acceptances, final schema hash, final process-owner hash, and both
focused-test hashes. C1A design SHA is
`491c98c56435d88f9f4f784942d28a5c29eeb838ac71b5d80e5657d26ef889de`; C1B design and
authorization SHAs are `d6ff76f71f25e322c7cdd6e70f51afcaedda2b86ab2446c1827075dc6d45d06c`
and `96b7d5c646c14e9526fe6f45e513e603788218cab4d76ef46c388365f6ff31d5`.

## 3. QPPR-A1 exact maximum-eight inventory

| # | Operation | Path | Frozen predecessor |
|---:|---|---|---|
| 1 | NEW | `scripts/testing/qa-provider-probe.py` | absent at `19c78faa` |
| 2 | MODIFY | `scripts/testing/smoke-flagship-cli-surfaces.sh` | `62705e40e0035e1f0c7d050f8e4ccd306a3343e01367468d3166c4a5ab97b261` |
| 3 | MODIFY | `scripts/testing/harness_qa/phases/phase0.py` | `fc43b959e2bbe6eb6753736df4818265616edace598d361fc93a5ddb929bf193` |
| 4 | MODIFY | `scripts/testing/harness_qa/core/result.py` | `d3272af4630a43bb2d0780074411a78339c7ed7cb3fb277892f18fb00c1ff8bd` |
| 5 | MODIFY | `scripts/testing/harness_qa/core/context.py` | `a2cf827b7d25c8ba234d87ae61de631145a67b821c2c086a9725ea0bab92cd80` |
| 6 | MODIFY | `scripts/testing/harness_qa/main.py` | `329627f7e417ddf7ead13a852860d8febeed85c111d1af9d41517b717356db37` |
| 7 | MODIFY | `scripts/testing/harness_qa/reporters/json_out.py` | `8629c57c7a5901871cca135c02f5a04d1a87a8250a9493316c56e6d8e0480fc5` |
| 8 | NEW | `scripts/testing/test-qa-provider-probe-adoption.py` | absent at `19c78faa` |

### 3.1 One aggregate and one invocation identity

`qa-provider-probe.py` is the sole aggregate runner. It loads the accepted policy, validates it
against the accepted schema, resolves only its four fixed executables from the supplied bounded
environment, and invokes `run_owned_process` sequentially exactly once per profile. The aggregate
ceiling is 200 seconds; each provider remains 45 seconds plus the frozen 2/1-second cleanup budgets.
No caller adds a shorter deadline.

Cross-process admission uses the repository-bound `.agent/qa/provider-probe.lock`. The runner opens
the already-owned `.agent/qa` directory with `O_DIRECTORY|O_NOFOLLOW`, then opens the lock relative
to that descriptor using `O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW`, mode `0600`, and **without**
`O_TRUNC`. Before and after nonblocking `flock(LOCK_EX|LOCK_NB)`, `fstat` plus directory-relative
`stat(..., follow_symlinks=False)` must prove one regular, single-link, effective-user-owned inode
with the same device/inode and no group/world write bits. The persistent lock inode is never
truncated, replaced, renamed, or unlinked. Kernel lock release handles owner death.

The owner holds that same descriptor from admission, through every provider attempt and heartbeat,
through the final terminal heartbeat and immutable-evidence publication handoff, until signal
restoration/redelivery or ordinary return cleanup. Normal, exception, cancellation, and custom-
handler paths release it exactly once. A contender never invokes C1/C1B, resolves a provider, writes
the heartbeat, attaches, signals, waits, retries, or changes the inode. It returns an exact four-item
details list in policy order, each item a closed no-spawn `qa.provider-probe-result.v1` with the
contender invocation ID and `failure_class=probe_busy`.

The runner supports a strict machine interface and an in-process Phase-0 API. Both use the same
policy loader, normalizer, result serializer, ordering, and exit decision. The CLI accepts no raw
argv, executable, timeout, retry, fallback, provider extension, environment override, prompt, or
network target. Tests inject a fixture-only resolver through an import-level test seam; production
CLI flags cannot select it.

`main.py` reserves the immutable `Invocation` before constructing `RunContext`. Context carries the
exact run ID, sequence, and start time plus interruption state to Phase 0. It never fabricates an
identity. Standalone compatibility execution returns machine output but cannot write the canonical
heartbeat or immutable QA evidence.

### 3.2 Closed typed evidence and interruption

`CheckResult.details` is either absent/`None` or one exact JSON-compatible list with **exactly four**
items in immutable policy order `codex,qwen,claude,pi`. Every item independently validates as the
closed `qa.provider-probe-result.v1`; its `provider_id`, profile, and invocation ID must match that
position and the reserved QA invocation. No envelope, arbitrary metadata, extra/missing/reordered
item, second schema, JSON-in-description, or result-shaped exception text is allowed.

Normal aggregates carry four actual terminal results. Aggregate lock contention carries four
deterministic no-spawn `probe_busy` results. On interruption, completed/current providers retain
their actual results and every not-started policy suffix receives a deterministic zero-duration,
no-action, no-spawn `interrupted` result at the aggregate interruption timestamp. Those suffix
records are evidence of aggregate cancellation, not provider starts; tests assert their spawn count
is zero. Thus partial, busy, and complete paths retain the same exact four-item shape.

One `CheckResult.to_dict()` serializer preserves the list byte-for-structure. `json_out.py` and
`main.py` consume that serializer instead of reconstructing dictionaries. Check `0.6.1`, machine
output, immutable publication, later API projection tests, and fixtures compare the same list.
Immutable publication binds it to the previously reserved invocation. A later invocation cannot
overwrite or relabel prior evidence.

SIGTERM/SIGINT during the aggregate follows the C1 controller: current process cleanup, bounded one
publication attempt using the exact four-item interrupted list, exact disposition/mask restoration,
and one redelivery. A second signal coalesces. No retry or next-provider start occurs. A1 consumes
only accepted C1B pipe events; it never synthesizes `terminating` or `reaping`. Missing/dropped C1B
events make the projection unavailable/degraded without changing lifecycle evidence.

### 3.2.1 One terminal-event/result join

For each attempted provider, `qa-provider-probe.py` creates exactly one in-memory
`TerminalProjectionJoin` owned by the aggregate main process. Its two inputs are:

1. the parsed, sequence-validated C1B `terminal` event, which C1B guarantees is emitted only after
   cleanup and normalization and before provisional publication/redelivery; and
2. one fully schema-validated C1 result—either the ordinary returned result or the provisional
   result delivered to C1's existing bounded publication callback.

The join accepts only matching invocation/provider/profile identity and the current expected C1B
terminal sequence. It derives `last_terminal_failure_class` only from the validated result, never
from timing, prior heartbeat state, stderr, exit status, or a synthesized cleanup state. Returned
and provisional results are idempotently equivalent for this join when their stable tuple
`(invocation_id, provider_id, profile_id, result, failure_class)` matches; later disposition,
redelivery, duration, action timestamp, or evidence-digest differences cannot trigger a second
projection write.

The state machine is closed and monotonic:

```text
OPEN -> HAVE_EVENT|HAVE_RESULT -> COMMITTING -> COMMITTED
OPEN|HAVE_* -> CANCELLED
```

Each input slot is compare-and-set once. Conflicting duplicate input cancels the join and emits no
terminal projection. Exactly one observer-consumer routine is the terminal-heartbeat writer; the
ordinary return path and provisional-publication callback only submit the result and invoke the same
`try_commit` operation. `COMMITTING` is acquired once under a process-local mutex, performs one C1A-
validated atomic replacement, then records `COMMITTED`; no other path writes terminal state.

On an ordinary return, the returned result and already ordered terminal event commit once before
the next provider starts. On SIGTERM/SIGINT, the provisional-publication callback submits the
normalized result, waits only for the already-preceding terminal event, calls the same `try_commit`,
and includes that completion in its existing bounded publication work before returning to C1.
Default redelivery occurs only after that callback returns or its existing publication remainder is
exhausted. Custom/ignored dispositions may later return a second result, which is an idempotent
no-op. The join is cancelled at callback deadline or immediately before redelivery/aggregate
teardown; a cancelled join rejects all later input and writes. The callback performs no retry,
background continuation, or unbounded wait, and the join cannot extend C1's four/five-second SLO.

If the terminal event was dropped because the observer pipe failed or the bounded publication
remainder cannot complete, the system records immutable typed evidence as C1 permits but emits no
fabricated terminal heartbeat; the last projection becomes stale/unavailable. This is a typed
projection-delivery failure, never a false terminal class. Acceptance fixtures with a functioning
observer/filesystem must prove one—and only one—terminal heartbeat before ordinary continuation or
default/custom/ignored redelivery, with the exact failure class and no write after redelivery.

### 3.3 Active projection and atomicity

Only invocation-bound Phase 0 may atomically replace
`.agent/qa/provider-probe-active.json`. Each object must validate against the accepted C1A
`qa.provider-probe-active.v1` contract before write. Heartbeats occur at start/state transition and
at least once per second while running. The writer uses a same-directory exclusive temporary file,
mode `0600`, bounded JSON, file flush/fsync, symlink/non-regular-target rejection, atomic replace,
and directory fsync. It uses the already validated directory descriptor and directory-relative
operations; it never pre-truncates the destination. Existing targets must be regular, single-link,
effective-user-owned, and not group/world writable. The unique temporary inode is opened
`O_WRONLY|O_CREAT|O_EXCL|O_CLOEXEC|O_NOFOLLOW`, fully written, flushed, fsynced, revalidated, then
atomically renamed over the destination and followed by directory fsync. Temp cleanup is
directory-relative and cannot touch the persistent lock inode.

The final terminal heartbeat remains a projection, not acceptance authority. The declared consumer
freshness threshold is **5 seconds**. Missing, malformed, unbound, future-dated, or older data is
`unavailable`/`stale`, never healthy. No PID, process identity, argv, executable, output, environment,
path, prompt, credential, model, or verdict enters the projection.

### 3.4 Adoption points

- `phase0.py` calls the runner directly for `0.6.1`; the old `cmd_ok(...timeout=15)` shell nesting is
  removed. Dashboard-safe mode keeps `0.6.1` as explicit host-only `SKIP` and never executes a
  provider.
- The compatibility shell validates its fixed prerequisites then `exec`s the Python runner. It has
  no GNU `timeout`, `--foreground`, `nohup`, `disown`, `eval`, command string, retry, or second
  lifecycle owner.
- The Python machine result, compatibility exit, Phase-0 result, JSON reporter, and immutable
  evidence share one terminal mapping.

## 4. QPPR-A2 exact maximum-five inventory

| # | Operation | Path | Frozen predecessor |
|---:|---|---|---|
| 1 | MODIFY | `dashboard/backend/api/services/qa_runner.py` | `abc105fc8caa7cc72fcc02df75e28ed930173741081cb88cdffb0769a26ec0e0` |
| 2 | MODIFY | `dashboard/backend/api/routes/aistack.py` | `8ae69185c83c4a55e8d41060078ea7575387cd0edd873988fdd9261f505b48db` |
| 3 | MODIFY | `dashboard.html` | `801a50b24c09879471771bac53ea31f34ee22ba5236cf96033dcaaa88cd93323` |
| 4 | MODIFY | `assets/dashboard.js` | `4e3b44cb0caa8a86988b1b2de68091df90ef4f51d09caccfc65cd9c05990c8b6` |
| 5 | NEW | `scripts/testing/test-dashboard-qa-provider-probe.py` | absent at `19c78faa` |

### 4.1 Bounded backend projection

`qa_runner.py` gains one pure bounded reader for the active file. It rejects non-regular/symlinked,
oversized, malformed, unknown-field/version/provider/state/class, invalid-time, unbound, and stale
objects. It returns a fixed `provider_probe` API object with only:

```text
availability       current|stale|unavailable
provider_id        closed provider or null
lifecycle_state    closed state or unavailable
elapsed_ms         bounded integer or null
last_failure_class closed class or null
freshness_ms       bounded integer or null
qa_invocation_id   UUID or null
host_execution     active|terminal|dashboard_confined_skip|unavailable
```

`aistack.py` adds a validated `projection_only=true` query mode to the existing
`/aq-qa/run/0` route. That branch calls only the bounded projection reader and returns only
`provider_probe`, a response timestamp, and `projection_only=true`. It returns **before** QA cache
lookup, background-task admission, `run_phase_json`, evidence access/mutation, provider execution,
or dashboard-confined normalization. It cannot start QA or refresh/mutate the 300-second QA cache.
The ordinary route may attach the same bounded object to cached/pending results, but the immutable
evidence result remains pass/fail authority; projection never changes counts, status, cache, or
acceptance. Dashboard confinement reports `dashboard_confined_skip`, never PASS.

### 4.2 Existing-card UI

`dashboard.html` adds exactly six rows with unique IDs and visible text labels: Active Provider,
Probe State, Probe Elapsed, Last Failure Class, Heartbeat Freshness, and Evidence Invocation.
`assets/dashboard.js` renders only allowlisted server fields through `setText`; it does not use
`innerHTML` for projection data. Missing, stale, malformed, and confined states render explicit
human-readable values, not blank `--` when evidence exists. Provider failure does not silently
overwrite the card's immutable Phase-0 PASS/FAIL badge.

A dedicated projection poller—not `loadQA()`—requests only
`/aistack/aq-qa/run/0?projection_only=true`. It performs one immediate read when the Operations panel
becomes visible, polls every **1 second** while state is active, and every **2 seconds** while idle,
terminal, stale, or unavailable. There is at most one in-flight request. Each request has its own
`AbortController` and 750 ms deadline; a superseded, hidden, or navigated-away request is cancelled.
Polling stops while the document is hidden or the Operations panel is inactive and resumes
immediately on visibility/panel entry. This bounds load while guaranteeing an externally started
host heartbeat reaches a visible card within two seconds and a one-second heartbeat is evaluated
inside the five-second freshness ceiling. Errors/staleness render explicitly and back off to the
two-second cadence; they never call the active QA route.

The rows use the existing `fw-row`/`fk`/`fv` vocabulary, contrast variables, density, and responsive
grid. Provider/state/failure values remain readable at normal and narrow viewport widths, long UUIDs
wrap or truncate with an accessible full-value label, keyboard navigation remains unchanged, and no
motion or visual redesign is introduced.

## 5. Atomic sequence, roles, and acceptance

1. C1A and C1B must each receive independent design review, explicit owner activation, one bounded
   implementation, exact-subject independent acceptance, and separate atomic commits.
2. The A1 design and authorization must then be amended/rebound to both exact accepted commits,
   acceptances, schema/process-owner/test hashes, and independently reviewed.
3. Owner activates A1 for exactly one bounded implementer. A different agent accepts the exact
   eight-file candidate. The orchestrator commits A1 but does not deploy or execute a real provider.
4. A2 must immediately follow: exact authorization activation, different bounded implementation,
   independent exact-subject acceptance, and the five-file commit. No unrelated commit may
   intervene between A1 and A2.
5. Only after both commits exist may a separate activation/vetting record authorize one bounded
   host Phase-0 run, API verification, browser verification, and deployment if needed.

The cheapest healthy eligible implementer model should own each bounded implementation. Implementers
cannot delegate, stage, commit, deploy, or self-accept. Review uses an independent flagship
architecture/security/SRE/QA team role against exact final hashes. Any reviewer edit creates a new
subject and requires another independent reviewer. Only the orchestrator stages and commits.

### A1 acceptance metrics

- Eight paths exactly; two new paths were absent and six predecessor hashes match.
- Fake-provider focused suite covers clean, nonzero, missing, deadline, stopped/forked, flood,
  `probe_busy`, interruption, stale/symlink heartbeat, and all one-spawn normalization branches.
- A real two-process fixture holds the stable aggregate lock in process A while process B contends;
  B returns four ordered `probe_busy` records, starts zero fake providers, writes no heartbeat, and
  cannot disturb A. Owner crash releases the advisory lock without replacing/unlinking its inode.
- Exactly four starts and zero retries per complete fake aggregate; interruption starts no later
  provider; zero owned descendants survive.
- Direct runner, compatibility shell, `CheckResult.to_dict`, JSON reporter, and captured immutable
  publication preserve the exact four-item policy-ordered list for complete, busy, and interrupted
  paths and agree byte-for-structure on provider ID, state, result, and failure class.
- Normal return plus default/custom/ignored SIGTERM/SIGINT fixtures deliver the terminal event and
  returned/provisional result in both input orders and under duplicate/conflicting races; each valid
  attempt writes exactly one C1A terminal heartbeat with the correct failure class, never before
  cleanup normalization, never after redelivery, and never by the result-submission path itself.
- Every canonical active run publishes a C1A-valid heartbeat within two seconds, then at least once
  per second; standalone and dashboard-safe paths write none.
- Python/shell syntax, focused tests, offline fake-path `aq-qa 0 --machine`, and Tier-0 pass without
  invoking real provider executables or network.

### A2 acceptance metrics

- Five paths exactly; the new test was absent and four predecessor hashes match the A1-adjacent
  branch state or an independently reviewed rebind records any changed predecessor.
- Reader rejects every malformed/stale/symlink/oversized/sensitive case and never changes QA counts.
- API golden cases cover passive pending, running, terminal pass/fail, stale, unavailable, and
  dashboard-confined skip with the exact bounded `provider_probe` object; spies prove projection-only
  reads never touch QA execution, cache mutation, evidence, provider resolution, or background tasks.
- Rendered card shows all six fields at desktop and narrow viewport, uses accessible labels, has no
  console errors, and never inserts projection values as HTML.
- A real browser fake-heartbeat fixture starts outside the dashboard process and reaches the visible
  DOM within two seconds; active refresh remains <=1 second, freshness classification <=5 seconds,
  only one request is in flight, hidden-panel cancellation works, and no active `/run/0` request is
  observed.
- Golden parity is 100% across heartbeat, API, and DOM for provider, state, failure, elapsed,
  freshness, and invocation; raw output/prompt/credential/PID/argv/path canaries are absent.
- Focused backend/frontend tests, Python compilation, JavaScript parse/lint checks, Tier-0, then the
  separately authorized live API/browser vet pass.

## 6. Mandatory stop conditions

Stop without workaround, partial handoff, or inferred authority on any inventory expansion,
substitution, predecessor drift, foreign dirty overlap, C1A/C1B absence or mismatch, schema relaxation,
unbounded file/read/output, alternate lifecycle/store/endpoint/card, new environment variable,
port, dependency, Nix/systemd/service/broker/cgroup change, retry/fallback, shell command
construction, shorter timeout, provider prompt or credential exposure, projection used as acceptance
authority, or any deletion/rollback/deploy/live traffic not explicitly granted.

A1 stops if C1A or C1B is not accepted and committed. A2 stops if the exact A1 commit and its consecutive
commit position are not provable. A failed A2 candidate leaves A1 committed but inactive and blocks
all deployment/live provider execution until a reviewed forward fix or separately authorized paired
rollback.

## 7. Rollback and exclusions

Rollback is paired and separately authorized: revert A2 first, then A1; preserve immutable evidence
and audit history; never kill by name, argv, PID guess, or process search. C1A/C1 may be reverted only
after all A1/A2 imports are removed. If visibility alone fails while lifecycle cleanup is sound,
prefer a reviewed forward A2 fix over restoring unsafe nested timeouts.

This packet authorizes no implementation, staging, commit, provider execution, network, heartbeat or
evidence write, dashboard/API mutation, deployment, service restart, traffic, cutover, or rollback.
QPPR-A3 remains undefined and unauthorized.

`RECORD: PREPARED_ONLY. C1A and C1B are the next pure prerequisites. A1/A2 implementation and all
live actions remain unauthorized.`
