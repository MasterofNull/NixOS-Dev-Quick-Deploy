# QPPR C1A/C1B and A1/A2 preparation — independent review R3

**Overall verdict:** **PASS**
**Reviewed:** 2026-07-18
**Role:** independent architecture, security, SRE, QA, and dashboard-contract reviewer
**Implementation authority:** none

This final preparation review retains the two earlier review records as immutable history:

- `QPPR-A1-A2-PREPARATION-REVIEW.md` —
  `62363c8ff8bc63f18bee86ffbc9e0eb9a53e9bc7dc8fac6629b5727ea65b3d01`;
- `QPPR-A1-A2-PREPARATION-REVIEW-R2.md` —
  `9fd74f6ed49d1fe30b4a3474881695e31a3114223647474006c76263a2eff035`.

## Exact reviewed subjects

| Subject | Verified SHA-256 | Verdict |
|---|---|---|
| `C1A-CONTRACT-AMENDMENT-DESIGN-PACKET.md` | `d6cb56fb81f854ce7a1ffa326700f338406930dd0356291b874be022c8425e9d` | **PASS (unchanged)** |
| `C1A-IMPLEMENTATION-AUTHORIZATION.md` | `76eefcb29970917c7f211fe1165fcb96524045814a89204304e06db8733055ac` | **PASS / PREPARED_ONLY** |
| `C1B-OBSERVER-INTERFACE-DESIGN-PACKET.md` | `645286d69fb91e176269ad8f231930bc33510b58bea7df49dfb186f952ea707d` | **PASS** |
| `C1B-IMPLEMENTATION-AUTHORIZATION.md` | `13560e06c98977e53a3d73092887a380ca4ae858265bbb942bbbfc64be5700f7` | **PASS / PREPARED_ONLY** |
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `236b20c6c884e2b08ce51d0437174d47897af03f957d10c26052027600882d05` | **PASS / blocked on accepted C1A+C1B** |
| `A1-IMPLEMENTATION-AUTHORIZATION.md` | `6f2f4a57a711696267f1cb61871673299f9dce07ed70cf673117e815d693d854` | **PASS / correctly not activatable** |
| `A2-IMPLEMENTATION-AUTHORIZATION.md` | `5ca4830ecab4d3f5a500dc692bcd160ff26006aeb2939dff13219938634ecca2` | **PASS / correctly not activatable** |

All seven hashes matched the request. The accepted C1 helper and all eleven existing C1B/A1/A2
implementation predecessors matched their declared hashes. All three NEW implementation paths were
absent, and no implementation-target dirty overlap was present.

## Final blocker closure

### Terminal event/result/failure-class join — PASS

`TerminalProjectionJoin` now freezes the exact synchronization contract omitted in Revision 2:

- its only inputs are the sequence-validated C1B terminal event and one closed-schema-valid returned
  or provisional C1 result;
- invocation, provider, profile, and expected sequence must match before a join is possible;
- failure class comes only from the validated result, never from elapsed time, stderr, exit status,
  prior projection, or inferred cleanup state;
- the stable result tuple makes the provisional and later returned forms idempotently equivalent
  despite disposition, redelivery, action-time, duration, or digest changes;
- input slots are compare-and-set once and the closed monotonic state machine permits only one
  transition through `COMMITTING` to `COMMITTED`;
- exactly one observer-consumer routine owns the terminal heartbeat write; result submission only
  supplies the other input and participates in the same bounded join;
- conflicting duplicates cancel rather than guessing, and missing/dropped events yield stale/
  unavailable projection rather than a fabricated terminal state.

Normal return waits for the truthful terminal event/result join before starting another provider.
On SIGTERM/SIGINT, C1B's terminal event precedes the existing provisional-publication callback; the
callback supplies the normalized result and includes bounded join completion in the existing
publication remainder. Default disposition therefore either commits exactly once before redelivery
or cancels without a late writer. Returning custom and ignored dispositions can later submit the
returned result only as an idempotent no-op. Non-returning custom behavior is already outside C1's
post-redelivery SLO, after the bounded join decision. Cancellation at the callback deadline or
immediately before redelivery/teardown rejects every later input and write.

The acceptance matrix covers both input orders, duplicates/conflicts, normal return, and default,
custom, and ignored SIGTERM/SIGINT. It requires the exact C1A terminal failure class, no terminal
write before cleanup normalization, no result-path writer, no second terminal write, and no write
after redelivery. This closes the remaining R1 integration defect without expanding the observer
record or weakening the four/five-second cleanup/redelivery bounds.

Implementation must preserve the packet's observer-only writer rule: a result-submission thread may
signal/wait on the bounded join, but it must not perform the atomic projection replacement itself.
That rule is already an explicit acceptance assertion and stop condition, so it is not an additional
design gate.

### Descriptor inheritance property — PASS

C1B no longer claims to infer descriptor provenance. It operationally requires `FD_CLOEXEC` on the
caller descriptor via `F_GETFD`, duplicates with close-on-exec semantics, verifies `FD_CLOEXEC` on
the duplicate, and separately enforces open write-only, nonblocking FIFO/pipe type. Missing
`FD_CLOEXEC` is the exact named pre-spawn rejection case. Invalid input neither closes nor mutates
the caller descriptor; the duplicate is non-inheritable and `close_fds=True` remains mandatory.

The focused tests now cover `missing_cloexec`, blocking/read-only/regular/closed/negative inputs,
caller and duplicate flags, fixture-provider non-observation, and duplicate closure across normal,
exception, and signal paths. This is measurable, implementation-independent, and correctly avoids
an unprovable inherited-origin assertion.

## Reconfirmed earlier contract closure

- **C1A:** the exact two-file closed heartbeat schema correction remains minimal and non-breaking.
- **Lifecycle observation:** fixed <=96-byte/`PIPE_BUF` ASCII events, closed ordered states,
  nonblocking main-thread writes, backpressure/error disablement, no callback/worker/acknowledgement,
  and no impact on lifecycle evidence or SLOs.
- **Cross-process admission:** stable repository-bound inode, directory-relative `O_NOFOLLOW`, no
  truncation/replacement/unlink, pre/post device/inode/owner/link/mode checks, nonblocking `flock`,
  full aggregate ownership, exact no-spawn `probe_busy`, two-process contention, and owner-death
  release.
- **Typed evidence:** exact four-item `codex,qwen,claude,pi` list for complete, busy, and interrupted
  outcomes, closed per-item validation, invocation/profile binding, zero-start suffix cancellation,
  and one shared byte-for-structure serializer into immutable evidence.
- **Heartbeat durability/privacy:** invocation-bound Phase 0 only, validated directory descriptor,
  exclusive bounded temp, fsync plus atomic replacement, target revalidation, no symlink/hardlink/
  ownership/mode weakness, five-second freshness, and no sensitive or high-cardinality fields.
- **Passive dashboard transport:** existing `/run/0?projection_only=true` branch returns before QA
  cache/task/evidence/execution behavior; single-flight visibility-aware cancellable polling meets
  the one/two/five-second contracts without a new endpoint or active QA trigger.
- **Service coverage and UI:** existing Phase-0 check and QA card, six accessible text-only fields,
  immutable evidence remains badge/count authority, dashboard confinement stays explicit SKIP,
  desktop/narrow browser evidence, and canary exclusion.
- **Atomicity and authority:** exact eight-file A1 and five-file A2 ceilings, consecutive but separate
  commits, independent implementation/acceptance, paired inactivity, paired rollback, no self-
  acceptance, and no provider/API/browser/deploy/live authority from these preparation records.

The passive route implementation test must retain the packet's `/run/0`-only meaning and reject a
projection-only request for any other phase before active-route effects. This follows directly from
the reviewed grant and does not add a file or new design requirement.

## Validation evidence

- Frozen subject hashes: **PASS, 7/7 exact**.
- Existing implementation predecessor hashes: **PASS, 11/11 exact**.
- NEW-path and target dirty-overlap scan: **PASS, three absent and no overlap**.
- Accepted C1 helper remains exact at
  `d458b1044850b336374745c28254a808aba153b16225eedb82396873bc844170`.
- The unchanged accepted C1 focused suite was run against that exact helper during the initial
  review: **PASS, 27/27 in 48.546 seconds**.
- Static control-flow verification reconfirmed provisional publication occurs before signal
  redelivery and that default redelivery can prevent an ordinary caller return—the exact race now
  covered by the join contract.
- Candidate documents contain no implementation, heartbeat/evidence write, provider resolution,
  route/UI mutation, deployment, traffic, or rollback action.

## Gate decision

`VERDICT: PASS`. C1A and C1B preparation packages are independently suitable for separate exact
owner activation and bounded implementation. A1/A2 design is approved but remains blocked until
both pure prerequisites are independently implemented, accepted, and committed. A1 then requires
the specified exact accepted-subject rebind and fresh review; A2 requires the accepted A1 adjacency
rebind and fresh review. This PASS authorizes no implementation, staging, commit, heartbeat/evidence
write, provider execution, network, API/browser action, deployment, traffic, rollback, deletion, or
self-activation.
