# QPPR-C1B lifecycle-observer interface authorization

**Authorization ID:** `auth-qa-provider-probe-reliability-c1b-20260718`
**Idempotency key:** `qa-provider-probe-reliability:c1b:observer-interface:v1:20260718`
**Status:** **PREPARED_ONLY / REVISION 2 — IMPLEMENTATION NOT AUTHORIZED**
**Prepared:** 2026-07-18
**Single use:** consumed by the first complete exact two-file candidate report

## 1. Exact bound subjects

| Subject | SHA-256 |
|---|---|
| `C1B-OBSERVER-INTERFACE-DESIGN-PACKET.md` | `d6ff76f71f25e322c7cdd6e70f51afcaedda2b86ab2446c1827075dc6d45d06c` |
| QPPR PRD | `7f4bf98c4962045c7da863994337cb41cf24798c3ab168ca19169e54f2bebf0d` |
| C1 implementation acceptance | `3f084c8af9ce53aced4ab40a190688756ed547954262a2277324bdccb541599c` |
| `scripts/testing/harness_qa/core/process_lifecycle.py` | `d458b1044850b336374745c28254a808aba153b16225eedb82396873bc844170` |
| `scripts/testing/test-qa-provider-probe-observer.py` | must be absent |

Committed basis: `19c78faaf5ab6d3635ac05a80fd5ba3c63cb1aae`. Any mismatch is a hard stop.

## 2. Exact grant

One bounded implementer may modify the accepted process owner and create the new focused observer
test—exactly two files. The helper may gain only optional `observer_fd: int | None`, exact
`FD_CLOEXEC`/write-only/nonblocking/FIFO validation and duplication, the fixed <=96-byte nonblocking
pipe-event emitter, exact state-transition calls including terminal-before-provisional-publication,
and cleanup needed to close its duplicate. All behavior and adversarial evidence must match the
bound design packet.

Existing lifecycle results, policy validation, normalization, sanitization, process identity,
cleanup order, signal controller, publication, four/five-second bounds, exports, and default behavior
when `observer_fd=None` remain compatible.

## 3. Mandatory stops

Stop without workaround on a third file, path substitution, predecessor drift, foreign dirty
overlap, callback/thread/queue/acknowledgement observer, blocking I/O, missing caller/duplicate
`FD_CLOEXEC` validation, unobservable provenance assertion, relaxed cleanup or signal SLO,
record expansion, new schema/policy/provider/profile/budget, real provider/network, heartbeat or
evidence write, Phase-0/shell/dashboard/backend/API/Nix/service/broker/cgroup/deploy/traffic action,
A1/A2 edit, staging, commit, rollback, or deletion.

The implementer cannot delegate, stage, commit, deploy, or self-accept. It reports both exact hashes,
objective/root cause, interface reasoning, exact offline test measurements, descriptor/process leak
checks, and exclusions. A reviewer edit changes the subject and recuses that reviewer.

## 4. Review and activation

Independent design/authorization review of this exact document is required first. Owner activation
must then name this authorization's exact SHA-256, exactly one implementer, activation and <=24-hour
expiry timestamps, and affirm the two-file ceiling and stops. Broad preauthorization, a review
`PASS`, silence, C1A activation, or A1/A2 direction does not activate C1B.

A different agent/session reviews exact final hashes and issues
`VERDICT: PASS|FAIL|REQUEST_REVISION`. Only the orchestrator stages and commits after both focused
suites, Python compilation, security/process-leak checks, and Tier-0 pass. No review or commit
activates A1/A2 or a provider path.

`RECORD: PREPARED_ONLY. C1B implementation and all adoption/live actions remain unauthorized.`
