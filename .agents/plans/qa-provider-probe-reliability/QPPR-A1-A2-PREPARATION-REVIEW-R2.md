# QPPR C1A/C1B and A1/A2 preparation — independent review R2

**Overall verdict:** **REQUEST_REVISION**
**Reviewed:** 2026-07-18
**Role:** independent architecture, security, SRE, QA, and dashboard-contract reviewer
**Implementation authority:** none

This review preserves and supersedes no history from
`QPPR-A1-A2-PREPARATION-REVIEW.md` SHA-256
`62363c8ff8bc63f18bee86ffbc9e0eb9a53e9bc7dc8fac6629b5727ea65b3d01`.
It evaluates only the new Revision-2 subjects and the unchanged C1A subjects named below.

## Exact reviewed subjects

| Subject | Verified SHA-256 | Verdict |
|---|---|---|
| `C1A-CONTRACT-AMENDMENT-DESIGN-PACKET.md` | `d6cb56fb81f854ce7a1ffa326700f338406930dd0356291b874be022c8425e9d` | **PASS (unchanged)** |
| `C1A-IMPLEMENTATION-AUTHORIZATION.md` | `76eefcb29970917c7f211fe1165fcb96524045814a89204304e06db8733055ac` | **PASS / PREPARED_ONLY** |
| `C1B-OBSERVER-INTERFACE-DESIGN-PACKET.md` | `68f813eec2f9b4cefa7b779b71fdea40d9984ab5e2650a13c6290700eccf3a18` | **REQUEST_REVISION** |
| `C1B-IMPLEMENTATION-AUTHORIZATION.md` | `b61387236a4e419d57af31cdca5f5a91d2108f336122f60ff66f3b4d86270ac6` | **REQUEST_REVISION** |
| `A1-A2-ADOPTION-DESIGN-PACKET.md` | `e4afeaba8b0c6d4b0300b9e870174779d36c99dcd6705907abbca495cf57669b` | **REQUEST_REVISION** |
| `A1-IMPLEMENTATION-AUTHORIZATION.md` | `0092ac9cd706d849a0196e549c1fba61caf82cdef40fa4364afbb5c6e9744b66` | **REQUEST_REVISION / correctly not activatable** |
| `A2-IMPLEMENTATION-AUTHORIZATION.md` | `e89b6af250e08fa34e61ea0a4305b51df818494f349b0a486bc1b5ab0165506b` | **APPROVE WITH REBIND / correctly not activatable** |

All seven hashes matched the review request. The accepted process owner and all eleven existing
C1B/A1/A2 implementation predecessors matched their declared hashes. The three declared NEW paths
were absent, and no implementation-target dirty overlap was present.

## Prior-finding closure

### R1 — Truthful lifecycle observation: architecture resolved, terminal join still incomplete

C1B correctly replaces callbacks and fabricated cleanup state with a descriptor-only, nonblocking,
fixed-record observer. Its bounded event vocabulary, exact ordering, main-thread writes, backpressure
failure behavior, descriptor non-inheritance, duplicate closure, and unchanged cleanup/redelivery
budgets are a sound lifecycle-observation architecture. A1 consumes rather than synthesizes
`terminating` and `reaping`. This resolves the central R1 architecture defect.

One exact join remains undefined. The C1A terminal heartbeat requires non-null
`last_terminal_failure_class`, but C1B's terminal record intentionally carries no failure/result.
On an ordinary return A1 can eventually join the terminal event with the returned result. On
SIGTERM/SIGINT with a restored default disposition, the helper publishes provisional evidence and
then re-delivers the signal; the outer A1 call may never return. Revision 2 does not say how the
observer consumer, the C1 bounded publication callback, and the heartbeat writer coordinate to
publish exactly one truthful terminal heartbeat before redelivery. Writing on the terminal event
alone lacks the class; waiting only for return loses the default-signal terminal projection; having
both independently write risks races or duplicate/out-of-order terminal publication.

**Required R1 revision:** freeze one idempotent terminal-join state machine. It must name the two
inputs (truthful C1B terminal sequence plus normalized returned/provisional C1 result), define the
single writer and CAS/once guard, cover normal return and default/custom/ignored redelivery, and
bound completion inside the existing publication remainder without delaying the four/five-second
SLO. Tests must prove exactly one terminal heartbeat with the correct failure class, no terminal
heartbeat before cleanup normalization, and no write after default redelivery. Alternatively, add
the closed failure class to the C1B terminal record and review that changed interface explicitly.

### R2 — Stable-inode cross-process ownership: PASS

The stable `.agent/qa/provider-probe.lock` contract now uses directory-relative `O_NOFOLLOW`, no
pre-lock truncation, device/inode/link/owner/mode verification before and after nonblocking `flock`,
one persistent non-replaced inode, full aggregate lifetime ownership, and kernel release on owner
death. Contention has an exact four-item no-spawn `probe_busy` result and cannot resolve, start,
attach, signal, wait, retry, or write the owner's heartbeat. The required real two-process contender
and owner-crash fixture closes the process-local-lock gap.

### R3 — Passive dashboard visibility and freshness: PASS

The existing route now has a precisely bounded `projection_only=true` branch that returns before QA
cache lookup, background admission, evidence access, normalization, or execution. It does not mutate
the 300-second cache. The dedicated single-flight poller has visibility/panel gating, per-request
cancellation, a 750-ms deadline, one-second active and two-second inactive cadence, explicit stale/
error rendering, and a browser fixture proving externally written fake heartbeat visibility without
an active QA request. This is sufficient to make the five-second freshness and two-second visible-
card target testable without a new endpoint or provider execution.

The implementation test should also assert that `projection_only=true` with any phase other than
`0` fails before all active-route effects. That is an expected consequence of the packet's
`/run/0`-only grant, not a new inventory requirement.

### R4 — Exact typed evidence shape: PASS

`CheckResult.details` is now exactly absent/`None` or a four-item list in immutable
`codex,qwen,claude,pi` policy order. Every item independently validates as the closed result object
and binds its provider/profile/invocation position. Complete, contention, and interrupted paths have
deterministic representations; suffix interruption records explicitly have zero starts. One shared
serializer preserves the exact structure through direct runner, Phase 0, JSON, and immutable
evidence. This closes the prior aggregate-shape ambiguity without inventing an open envelope.

## Additional C1B contract correction

C1B acceptance requires an “inherited descriptor” to fail closed, but the interface does not define
an observable inherited condition. Descriptor provenance cannot be inferred from FIFO type,
access mode, or nonblocking status; an inherited descriptor can have the same properties as a
caller-created one. The packet mentions caller-created `O_CLOEXEC`, while its validation list only
requires write-only, nonblocking FIFO/pipe and says the helper's duplicate gains close-on-exec.

**Required correction:** operationally define this case—for example, require and verify
`FD_CLOEXEC` on the caller descriptor and rename the fixture to `missing_cloexec`—or remove the
unprovable provenance claim. Continue duplicating to a non-inheritable descriptor and retain
`close_fds=True`. The design and authorization must agree on the exact pre-spawn validation.

## Other boundaries that pass

- C1A remains the minimal two-file, pure-schema correction and retains its prior PASS.
- C1B's two-file ceiling is orthogonal to C1A and preserves default C1 behavior with
  `observer_fd=None`.
- A1 maximum-eight and A2 maximum-five inventories remain exact and predecessor-bound.
- The heartbeat writer is directory-relative, exclusive-temp, bounded, fsynced, single-link/
  owner/mode checked, symlink-safe, and never mutates the persistent lock inode.
- A1/A2 remain consecutive but atomic, independently implemented/reviewed, inactive until paired,
  and separate from live provider/API/browser/deployment authorization.
- Immutable evidence remains authority; heartbeat/API/DOM remain low-cardinality projections and
  exclude prompts, credentials, outputs, process identity, argv, environment, paths, models, and
  verdicts.
- Fake-only implementation tests, service coverage, accessible text-only rendering, paired
  rollback, no kill-by-guess, no self-acceptance, and stop conditions remain appropriately strict.

## Validation evidence

- Frozen subject hashes: **PASS, 7/7 exact**.
- Existing C1B/A1/A2 implementation predecessor hashes: **PASS, 11/11 exact**.
- Declared NEW paths and dirty-overlap scan: **PASS, three absent and no target overlap**.
- Accepted C1 helper remained exact at
  `d458b1044850b336374745c28254a808aba153b16225eedb82396873bc844170`.
- Existing C1 focused lifecycle suite was executed against that exact helper during the first review:
  **PASS, 27/27 in 48.546 seconds**. No implementation changed between reviews.
- Static control-flow review confirmed default-signal redelivery can terminate before the caller
  returns and that the provisional publication callback precedes redelivery.
- Markdown/diff validation: required after this record is written; no candidate file was edited.

## Gate decision

`VERDICT: REQUEST_REVISION`. R2, R3, and R4 are closed. R1's observation transport is sound, but
the terminal event/result join and descriptor-provenance acceptance rule require the two bounded
clarifications above. C1A may proceed through its already reviewed explicit owner-activation gate.
C1B, A1, and A2 must remain unactivated; any revised A1/A2 subject must rebind A2 even though its
standalone dashboard design passes. This review authorizes no implementation, staging, commit,
heartbeat/evidence write, provider execution, network, API/browser action, deployment, traffic,
rollback, deletion, or self-activation.
